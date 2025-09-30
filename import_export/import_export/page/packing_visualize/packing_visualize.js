// Load Three.js and OrbitControls from app's public folder

// Global variables for 3D scene management
window.packing_3d_cleanup = null;
window.packing_explosion_factor = 0;

function loadThreeJS(callback) {
	if (typeof THREE !== 'undefined' && typeof THREE.OrbitControls !== 'undefined') {
		callback();
		return;
	}

	// Load Three.js from app public folder
	frappe.require('/assets/import_export/js/libs/three.min.js', function() {
		// Load OrbitControls from app public folder
		frappe.require('/assets/import_export/js/libs/OrbitControls.js', callback);
	});
}

frappe.pages['packing-visualize'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Packing Visualization',
		single_column: true
	});
	// Store page reference
	frappe.packing_visualization = page;
	// Get pick list from route
	var pick_list = frappe.route_options?.pick_list || frappe.get_route()[1];
	if (!pick_list) {
		frappe.msgprint('Pick List name is required');
		frappe.set_route('List', 'Pick List');
		return;
	}
	// Set page title with pick list name
	page.set_title(`Packing Visualization - ${pick_list}`);
	// Add primary action
	page.set_primary_action('Back to Pick List', function() {
		frappe.set_route('Form', 'Pick List', pick_list);
	}, 'left');
	// Add secondary actions
	page.add_action_icon('refresh', function() {
		loadPackingData();
	}, 'Refresh', 'octicon octicon-sync');
	// Create layout
	createPackingLayout(page, pick_list);
	// Load initial data
	loadPackingData();
};

function createPackingLayout(page, pick_list) {
	// Store pick list name globally
	window.packing_pick_list = pick_list;
	window.packing_current_carton = 0;
	window.packing_current_view = '3d';
	// Create main layout
	var main_section = $(`
	<div class="packing-main-container">
	<div class="row">
	<!-- Sidebar -->
	<div class="col-md-3">
	<div class="packing-sidebar">
	<!-- Summary Card -->
	<div class="frappe-card">
	<div class="frappe-card-head">
	<h6>Packing Summary</h6>
	</div>
	<div class="frappe-card-body">
	<div id="packing-summary" class="packing-summary-grid">
	<div class="loading-text">Loading summary...</div>
	</div>
	</div>
	</div>
	<!-- Carton List Card -->
	<div class="frappe-card" style="margin-top: 15px;">
	<div class="frappe-card-head">
	<h6>Carton Assignments</h6>
	</div>
	<div class="frappe-card-body">
	<div id="carton-list">
	<div class="loading-text">Loading cartons...</div>
	</div>
	</div>
	</div>
	<!-- Current Carton Details -->
	<div class="frappe-card" style="margin-top: 15px;">
	<div class="frappe-card-head">
	<h6>Current Carton</h6>
	</div>
	<div class="frappe-card-body">
	<div id="carton-details">
	<div class="text-muted">Select a carton to view details</div>
	</div>
	</div>
	</div>
	</div>
	</div>
	<!-- Main Content -->
	<div class="col-md-9">
	<div class="frappe-card border">
	<div class="frappe-card-head">
	<div class="flex">
		<div class="flex-grow-1 pl-3 py-2">
			<h6>Visualization</h6>
		</div>
		<div class="col-md-6 text-right">
			<div class="btn-group btn-group-sm mb-2" role="group">
				<button type="button" class="btn btn-secondary active" id="view-3d" onclick="switchView('3d')">
					<i class="fa fa-cube"></i> 3D View
				</button>
				<button type="button" class="btn btn-secondary" id="view-2d" onclick="switchView('2d')">
					<i class="fa fa-map"></i> 2D Blueprint
				</button>
			</div>
		</div>
	</div>
	</div>
	<div class="frappe-card-body">
	<div id="packing-visualization-root" style="height: 500px; border: 1px solid var(--border-color); border-radius: 3px; background: var(--bg-color);">
	<div class="loading-container">
	<div style="text-align: center; padding-top: 200px; color: var(--text-on-gray);">
	<i class="fa fa-spinner fa-spin fa-2x" style="margin-bottom: 20px;"></i>
	<div>Loading packing visualization...</div>
	</div>
	</div>
	</div>
	</div>
	</div>
	</div>
	</div>
	</div>
	`);
	// Append to page
	main_section.appendTo(page.main);
	// Add custom styles
	addPackingStyles();
}

function loadPackingData() {
	frappe.call({
		method: 'import_export.packing_system.pick_list_packing.get_pick_list_packing_data',
		args: {
			pick_list_name: window.packing_pick_list
		},
		callback: function(r) {
			if (r.message && r.message.success) {
				window.packing_data = r.message;
				renderPackingSummary();
				renderCartonList();
				loadVisualization();
			} else {
				showError('Failed to load packing data');
			}
		},
		error: function() {
			showError('Error loading packing data');
		}
	});
}

function selectCarton(index) {
	window.packing_current_carton = index;
	renderCartonList();
	loadVisualization();
}

function switchView(view) {
	window.packing_current_view = view;
	$('#view-3d').toggleClass('active', view === '3d');
	$('#view-2d').toggleClass('active', view === '2d');
	loadVisualization();
}

function renderVisualization() {
	var data = window.packing_visualization_data;
	var view = window.packing_current_view;

	if (!data || !data.carton) {
		showError('No visualization data available');
		return;
	}
	var container = $('#packing-visualization-root');
	container.empty();
	if (view === '3d') {
		render3DVisualization(container, data);
	} else {
		render2DVisualization(container, data);
	}
}

function showError(message) {
	$('#packing-visualization-root').html(`
	<div style="text-align: center; padding-top: 200px; color: #d32f2f;">
	<i class="fa fa-exclamation-triangle fa-2x" style="margin-bottom: 20px;"></i>
	<h4>Error</h4>
	<p>${message}</p>
	</div>
	`);
}

function addPackingStyles() {
	$('<style>').prop('type', 'text/css').html(`
	.packing-main-container {
		margin: 0;
	}

	.packing-sidebar .frappe-card {
		border: 1px solid var(--border-color);
		border-radius: 3px;
	}

	.packing-sidebar .frappe-card-head {
		padding: 15px;
		border-bottom: 1px solid var(--border-color);
		background: var(--bg-color);
	}

	.packing-sidebar .frappe-card-body {
		padding: 15px;
	}

	.packing-summary-grid .packing-stat {
		text-align: center;
		padding: 8px;
		background: var(--bg-color);
		border-radius: 3px;
		margin-bottom: 5px;
	}

	.packing-stat .stat-label {
		font-size: 11px;
		color: var(--text-on-gray);
		margin-bottom: 3px;
	}

	.packing-stat .stat-value {
		font-size: 14px;
		font-weight: 600;
		color: var(--text-color);
	}

	.carton-item {
		padding: 10px;
		border: 1px solid var(--border-color);
		border-radius: 3px;
		margin-bottom: 5px;
		cursor: pointer;
		transition: all 0.2s;
	}

	.carton-item:hover {
		background: var(--bg-color);
		border-color: #5e64ff;
	}

	.carton-item.active {
		background: #5e64ff;
		color: white;
		border-color: #5e64ff;
	}

	.carton-item .carton-name {
		font-weight: 600;
		margin-bottom: 3px;
		font-size: 13px;
	}

	.carton-item .carton-stats {
		font-size: 11px;
		opacity: 0.8;
	}

	.carton-item.active .carton-stats {
		color: rgba(255,255,255,0.9);
	}

	.loading-text {
		text-align: center;
		color: var(--text-on-gray);
		padding: 20px;
	}

	.explosion-slider-container {
		position: absolute;
		top: 10px;
		right: 10px;
		background: var(--bg-light-gray);
		border: 1px solid #1565C0;
		border-radius: 4px;
		padding: 12px;
		min-width: 200px;
		z-index: 10;
		box-shadow: 0 2px 4px rgba(0,0,0,0.1);
	}

	.explosion-slider-container .slider-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 8px;
	}

	.explosion-slider-container .slider-label {
		font-size: 12px;
		font-weight: 600;
		color: #1565C0;
	}

	.explosion-slider-container .slider-value {
		font-size: 11px;
		color: #1976D2;
	}

	.explosion-slider-container input[type="range"] {
		width: 100%;
		margin: 0;
	}

	.explosion-slider-container .slider-help {
		font-size: 10px;
		color: #1976D2;
		margin-top: 6px;
		line-height: 1.3;
	}
	`).appendTo('head');
}

function renderPackingSummary() {
	var data = window.packing_data;
	var html = `
	<div class="row">
	<div class="col-xs-6">
	<div class="packing-stat">
	<div class="stat-label">Total Cartons</div>
	<div class="stat-value">${data.total_cartons || 0}</div>
	</div>
	</div>
	<div class="col-xs-6">
	<div class="packing-stat">
	<div class="stat-label">Unique Patterns</div>
	<div class="stat-value">${data.unique_patterns || 0}</div>
	</div>
	</div>
	</div>
	<div class="row" style="margin-top: 10px;">
	<div class="col-xs-6">
	<div class="packing-stat">
	<div class="stat-label">Avg Efficiency</div>
	<div class="stat-value">${(data.average_efficiency || 0).toFixed(1)}%</div>
	</div>
	</div>
	<div class="col-xs-6">
	<div class="packing-stat">
	<div class="stat-label">Total Cost</div>
	<div class="stat-value">${(data.total_packing_cost || 0).toFixed(2)}</div>
	</div>
	</div>
	</div>
	`;

	$('#packing-summary').html(html);
}

function renderCartonList() {
	var data = window.packing_data;
	if (!data.carton_assignments || data.carton_assignments.length === 0) {
		$('#carton-list').html('<div class="text-muted">No carton assignments found</div>');
		return;
	}
	var html = '';
	data.carton_assignments.forEach(function(assignment, index) {
		var isActive = index === window.packing_current_carton;
		var countLabel = assignment.carton_count > 1 ? ` (×${assignment.carton_count})` : '';
		var itemsPerCarton = assignment.items_per_carton || 0;
		html += `
		<div class="carton-item ${isActive ? 'active' : ''}" onclick="selectCarton(${index})">
		<div class="carton-name">${assignment.carton_name}${countLabel}</div>
		<div class="carton-stats">
		${itemsPerCarton} items/carton • ${(assignment.efficiency || 0).toFixed(1)}% efficiency
		</div>
		</div>
		`;
	});
	$('#carton-list').html(html);
	updateCartonDetails();
}

function updateCartonDetails() {
	var data = window.packing_data;
	var assignment = data.carton_assignments[window.packing_current_carton];
	if (!assignment) {
		$('#carton-details').html('<div class="text-muted">No carton selected</div>');
		return;
	}
	var carton = assignment.carton;
	var html = `
	<table class="table table-condensed">
	<tr><td>Carton:</td><td>${carton.length}×${carton.width}×${carton.height}cm</td></tr>
	<tr><td>Pattern Count:</td><td>×${assignment.carton_count || 1}</td></tr>
	<tr><td>Items/Carton:</td><td>${assignment.items_per_carton || 0}</td></tr>
	<tr><td>Efficiency:</td><td>${(assignment.efficiency || 0).toFixed(1)}%</td></tr>
	<tr><td>Material:</td><td>${carton.material || 'Standard'}</td></tr>
	</table>
	`;
	$('#carton-details').html(html);
}

function loadVisualization() {
	$('#packing-visualization-root').html(`
	<div class="loading-container">
	<div style="text-align: center; padding-top: 200px; color: var(--text-on-gray);">
	<i class="fa fa-spinner fa-spin fa-2x" style="margin-bottom: 20px;"></i>
	<div>Loading visualization...</div>
	</div>
	</div>
	`);

	frappe.call({
		method: 'import_export.packing_system.pick_list_packing.get_pick_list_3d_data',
		args: {
			pick_list_name: window.packing_pick_list,
			carton_idx: window.packing_current_carton
		},
		callback: function(r) {
			if (r.message) {
				window.packing_visualization_data = r.message;
				console.log('3D data received:', r.message);

				// Show pattern info if available
				if (r.message.pattern_info && r.message.pattern_info.carton_count > 1) {
					var msg = `Showing 1 carton pattern (repeats ${r.message.pattern_info.carton_count} times)`;
					frappe.show_alert({
						message: msg,
						indicator: 'blue'
					}, 5);
				}

				renderVisualization();
			} else {
				showError('No visualization data available');
			}
		},
		error: function(err) {
			console.error('Visualization API error:', err);
			showError('Error loading visualization data: ' + (err.message || 'Unknown error'));
		}
	});
}


function render3DVisualization(container, data) {
	if (window.packing_3d_cleanup) {
		window.packing_3d_cleanup();
		window.packing_3d_cleanup = null;
	}

	container.html(`
	<div id="threejs-container" style="width: 100%; height: 500px; position: relative;">
		<div class="explosion-slider-container">
			<div class="slider-header">
				<span class="slider-label">Exploded View</span>
				<span class="slider-value" id="explosion-value">Normal</span>
			</div>
			<input type="range" id="explosion-slider" min="0" max="3" step="0.1" value="${window.packing_explosion_factor||0}" />
			<div class="slider-help">Slide to spread carton sides and items apart for better visualization</div>
		</div>
	</div>
	`)

	var mountElement = container.find('#threejs-container')[0];

	if (typeof THREE === 'undefined') {
		container.html(`
		<div style="text-align: center; padding-top: 200px; color: #d32f2f;">
		<i class="fa fa-exclamation-triangle fa-2x" style="margin-bottom: 20px;"></i>
		<h4>Loading 3D Engine...</h4>
		<p>Please wait while Three.js loads.</p>
		</div>
		`);
		loadThreeJS(function() {
			render3DVisualization(container, data);
		});
		return;
	}

	try {
		// Detect dark mode
		var isDarkMode = document.body.classList.contains('dark') ||
		document.documentElement.getAttribute('data-theme') === 'dark';
		var scene = new THREE.Scene();
		scene.background = new THREE.Color(isDarkMode ? 0x1a1a1a : 0xf8f9fa);
		var camera = new THREE.PerspectiveCamera(75, container.width() / 500, 0.1, 1000);
		var renderer = new THREE.WebGLRenderer({ antialias: true });
		renderer.setSize(container.width() - 2, 498);
		renderer.shadowMap.enabled = true;
		renderer.shadowMap.type = THREE.PCFSoftShadowMap;
		mountElement.appendChild(renderer.domElement);

		var controls;
		if (typeof THREE.OrbitControls !== 'undefined') {
			controls = new THREE.OrbitControls(camera, renderer.domElement);
			controls.enableDamping = true;
			controls.dampingFactor = 0.05;
			controls.enablePan = true;
			controls.enableZoom = true;
			controls.enableRotate = true;
			controls.maxPolarAngle = Math.PI;
			controls.minDistance = 10;
			controls.maxDistance = 500;
		}

		// Adjust lighting for dark mode
		var ambientLight = new THREE.AmbientLight(0x404040, isDarkMode ? 0.8 : 0.6);
		scene.add(ambientLight);
		var directionalLight = new THREE.DirectionalLight(0xffffff, isDarkMode ? 1.0 : 0.8);
		directionalLight.position.set(50, 50, 50);
		directionalLight.castShadow = true;
		scene.add(directionalLight);

		// Explosion slider handler
		var explosionSlider = $('#explosion-slider');
		var explosionValue = $('#explosion-value');

		explosionSlider.on('input', function() {
			window.packing_explosion_factor = parseFloat(this.value);
			var displayValue = window.packing_explosion_factor === 0 ? 'Normal' : window.packing_explosion_factor.toFixed(1) + 'x';
			explosionValue.text(displayValue);
			renderScene();
		});

		var patterns = data.patterns || [];

		// Function to render the scene based on current explosion factor
		function renderScene() {
			// Clear existing objects (except lights and camera)
			var objectsToRemove = [];
			for (var i = 0; i < scene.children.length; i++) {
				var obj = scene.children[i];
				if (obj !== ambientLight && obj !== directionalLight && obj !== camera) {
					objectsToRemove.push(obj);
				}
			}
			// Remove all collected objects
			for (var i = 0; i < objectsToRemove.length; i++) {
				scene.remove(objectsToRemove[i]);
			}

			var explosionAmount = window.packing_explosion_factor;

			// Check if we have multiple patterns
			var showMultiple = data.show_multiple || false;

			if (patterns.length === 0) {
				console.log('No pattern data available');
				return;
			}

			// Calculate spacing for side-by-side layout
			var xOffset = 0;
			var spacing = data.carton.length + 30;
			var totalWidth = patterns.length * data.carton.length + (patterns.length - 1) * 30;

			// Render each pattern
			patterns.forEach(function(pattern, patternIdx) {
				renderExplodedCartonFaces(scene, data.carton, explosionAmount, isDarkMode);

				// Add label if multiple patterns
				if (showMultiple) {
					addTextLabel(
						scene,
				  'Pattern ' + (patternIdx + 1) + ' (×' + pattern.carton_count + ')',
								 xOffset + data.carton.length / 2,
				  data.carton.height + 15,
				  data.carton.width / 2
					);
				}

				// Parse positions
				var positions_3d = pattern.positions_3d;
				if (typeof positions_3d === 'string') {
					try {
						positions_3d = JSON.parse(positions_3d);
					} catch (e) {
						console.error('Failed to parse positions_3d:', e);
						positions_3d = {};
					}
				}

				// Render items for this pattern
				if (positions_3d && Object.keys(positions_3d).length > 0) {
					Object.keys(positions_3d).forEach(function(itemCode) {
						var positions = positions_3d[itemCode];
						var itemInfo = data.item_info[itemCode];

						if (!positions || !itemInfo) return;

						var color = new THREE.Color(itemInfo.color || '#3498db');

						positions.forEach(function(pos) {
							var itemGeometry = new THREE.BoxGeometry(
								pos.length || itemInfo.length,
								pos.height || itemInfo.height,
								pos.width || itemInfo.width
							);
							var itemMaterial = new THREE.MeshLambertMaterial({
								color: color,
								transparent: true,
								opacity: 0.8
							});
							var itemMesh = new THREE.Mesh(itemGeometry, itemMaterial);

							// Calculate base position
							var basePos = {
								x: xOffset + pos.x + (pos.length || itemInfo.length) / 2,
										  y: pos.z + (pos.height || itemInfo.height) / 2,
										  z: pos.y + (pos.width || itemInfo.width) / 2
							};

							// Apply explosion if enabled
							var finalPos = basePos;
							if (explosionAmount > 0) {
								finalPos = getExplodedPosition(basePos, data.carton, explosionAmount);
							}

							itemMesh.position.set(finalPos.x, finalPos.y, finalPos.z);
							scene.add(itemMesh);

							// Add edges
							var itemEdgesGeometry = new THREE.EdgesGeometry(itemGeometry);
							var itemEdgesMaterial = new THREE.LineBasicMaterial({
								color: color.clone().multiplyScalar(2)
							});
							var itemEdges = new THREE.LineSegments(itemEdgesGeometry, itemEdgesMaterial);
							itemEdges.position.copy(itemMesh.position);
							scene.add(itemEdges);

							// Add text labels to all faces
							addItemFaceLabels(
								scene,
								itemMesh,
								itemCode,
								pos.length || itemInfo.length,
								pos.height || itemInfo.height,
								pos.width || itemInfo.width
							);
						});
					});
				}

				// Move to next position
				xOffset += spacing;
			});
		}

		// Initial render
		renderScene();

		// Position camera to see all patterns
		var centerX = (patterns.length * data.carton.length + (patterns.length - 1) * 30) / 2;
		var maxDim = Math.max(data.carton.length, data.carton.width, data.carton.height);
		var distance = Math.max(maxDim * 2, centerX * 1.4);

		camera.position.set(centerX + distance * 0.7, distance * 0.7, distance * 0.7);
		camera.lookAt(centerX, data.carton.height / 2, data.carton.width / 2);

		// Animation loop
		var animationId;
		function animate() {
			animationId = requestAnimationFrame(animate);
			if (controls) controls.update();
			renderer.render(scene, camera);
		}
		animate();
		// Watch for theme changes and re-render
		var themeObserver = new MutationObserver(function(mutations) {
			mutations.forEach(function(mutation) {
				if (mutation.attributeName === 'data-theme' || mutation.attributeName === 'class') {
					// Theme changed, re-render
					renderVisualization();
				}
			});
		});

		// Observe theme changes on body and html
		themeObserver.observe(document.body, { attributes: true, attributeFilter: ['class'] });
		themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'class'] });

		// Cleanup
		window.packing_3d_cleanup = function() {
			if (animationId) {
				cancelAnimationFrame(animationId);
			}
			if (controls) {
				controls.dispose();
			}
			if (mountElement && renderer.domElement) {
				mountElement.removeChild(renderer.domElement);
			}
			renderer.dispose();
			themeObserver.disconnect();
		};
	} catch (error) {
		console.error('3D visualization error:', error);
		container.html(`
		<div style="text-align: center; padding-top: 200px; color: #d32f2f;">
		<i class="fa fa-exclamation-triangle fa-2x" style="margin-bottom: 20px;"></i>
		<h4>3D Visualization Error</h4>
		<p>${error.message}</p>
		</div>
		`);
	}
}

// Helper function to calculate exploded position for an item
function getExplodedPosition(originalPos, carton, explosionAmount) {
	var centerX = carton.length / 2;
	var centerY = carton.height / 2;
	var centerZ = carton.width / 2;

	var dirX = originalPos.x - centerX;
	var dirY = originalPos.y - centerY;
	var dirZ = originalPos.z - centerZ;

	var distance = Math.sqrt(dirX * dirX + dirY * dirY + dirZ * dirZ);
	if (distance === 0) return originalPos;

	var normalizedX = dirX / distance;
	var normalizedY = dirY / distance;
	var normalizedZ = dirZ / distance;

	var explosionDistance = explosionAmount * 10;

	return {
		x: originalPos.x + normalizedX * explosionDistance,
		y: originalPos.y + normalizedY * explosionDistance,
		z: originalPos.z + normalizedZ * explosionDistance
	};
}

// Helper function to render exploded carton faces
function renderExplodedCartonFaces(scene, carton, explosionAmount, isDarkMode) {
	var length = carton.length;
	var width = carton.width;
	var height = carton.height;
	var centerX = length / 2;
	var centerY = height / 2;
	var centerZ = width / 2;

	var explosionDistance = explosionAmount * 20;
	var edgeColor = isDarkMode ? 0xe0e0e0 : 0x000000; //0xcccccc

	var faceGeometry = new THREE.PlaneGeometry(1, 1);
	var faceMaterial = new THREE.MeshBasicMaterial({
		color: edgeColor,
		transparent: true,
		opacity: 0.15,
		side: THREE.DoubleSide,
		wireframe: true,
	});
	var edgeMaterial = new THREE.LineBasicMaterial({ color: edgeColor, linewidth: 1 });

	// Front face (Z+)
	var frontFace = new THREE.Mesh(faceGeometry.clone(), faceMaterial.clone());
	frontFace.scale.set(length, height, 1);
	frontFace.position.set(centerX, centerY, width + explosionDistance);
	scene.add(frontFace);
	var frontEdges = new THREE.EdgesGeometry(frontFace.geometry);
	var frontLine = new THREE.LineSegments(frontEdges, edgeMaterial);
	frontLine.position.copy(frontFace.position);
	frontLine.scale.copy(frontFace.scale);
	scene.add(frontLine);

	// Back face (Z-)
	var backFace = new THREE.Mesh(faceGeometry.clone(), faceMaterial.clone());
	backFace.scale.set(length, height, 1);
	backFace.position.set(centerX, centerY, -explosionDistance);
	scene.add(backFace);
	var backEdges = new THREE.EdgesGeometry(backFace.geometry);
	var backLine = new THREE.LineSegments(backEdges, edgeMaterial);
	backLine.position.copy(backFace.position);
	backLine.scale.copy(backFace.scale);
	scene.add(backLine);

	// Right face (X+)
	var rightFace = new THREE.Mesh(faceGeometry.clone(), faceMaterial.clone());
	rightFace.scale.set(width, height, 1);
	rightFace.rotation.y = Math.PI / 2;
	rightFace.position.set(length + explosionDistance, centerY, centerZ);
	scene.add(rightFace);
	var rightEdges = new THREE.EdgesGeometry(rightFace.geometry);
	var rightLine = new THREE.LineSegments(rightEdges, edgeMaterial);
	rightLine.position.copy(rightFace.position);
	rightLine.scale.copy(rightFace.scale);
	rightLine.rotation.copy(rightFace.rotation);
	scene.add(rightLine);

	// Left face (X-)
	var leftFace = new THREE.Mesh(faceGeometry.clone(), faceMaterial.clone());
	leftFace.scale.set(width, height, 1);
	leftFace.rotation.y = Math.PI / 2;
	leftFace.position.set(-explosionDistance, centerY, centerZ);
	scene.add(leftFace);
	var leftEdges = new THREE.EdgesGeometry(leftFace.geometry);
	var leftLine = new THREE.LineSegments(leftEdges, edgeMaterial);
	leftLine.position.copy(leftFace.position);
	leftLine.scale.copy(leftFace.scale);
	leftLine.rotation.copy(leftFace.rotation);
	scene.add(leftLine);

	// Top face (Y+)
	var topFace = new THREE.Mesh(faceGeometry.clone(), faceMaterial.clone());
	topFace.scale.set(length, width, 1);
	topFace.rotation.x = Math.PI / 2;
	topFace.position.set(centerX, height + explosionDistance, centerZ);
	scene.add(topFace);
	var topEdges = new THREE.EdgesGeometry(topFace.geometry);
	var topLine = new THREE.LineSegments(topEdges, edgeMaterial);
	topLine.position.copy(topFace.position);
	topLine.scale.copy(topFace.scale);
	topLine.rotation.copy(topFace.rotation);
	scene.add(topLine);

	// Bottom face (Y-)
	var bottomFace = new THREE.Mesh(faceGeometry.clone(), faceMaterial.clone());
	bottomFace.scale.set(length, width, 1);
	bottomFace.rotation.x = Math.PI / 2;
	bottomFace.position.set(centerX, -explosionDistance, centerZ);
	scene.add(bottomFace);
	var bottomEdges = new THREE.EdgesGeometry(bottomFace.geometry);
	var bottomLine = new THREE.LineSegments(bottomEdges, edgeMaterial);
	bottomLine.position.copy(bottomFace.position);
	bottomLine.scale.copy(bottomFace.scale);
	bottomLine.rotation.copy(bottomFace.rotation);
	scene.add(bottomLine);
}

// Helper function to add text labels to all 6 faces of an item
function addItemFaceLabels(scene, itemMesh, itemCode, itemLength, itemHeight, itemWidth) {
	var labelOffset = 0.01;
	var itemMaterial = itemMesh.material;
	var itemColor = itemMaterial.color;

	// Front face (Z+)
	var frontTexture = createTextTexture(itemCode, itemLength * 10, itemHeight * 10, itemColor);
	if (frontTexture) {
		var frontGeometry = new THREE.PlaneGeometry(itemLength, itemHeight);
		var frontMaterial = new THREE.MeshBasicMaterial({
			map: frontTexture,
			transparent: true,
			side: THREE.DoubleSide
		});
		var frontLabel = new THREE.Mesh(frontGeometry, frontMaterial);
		frontLabel.position.set(
			itemMesh.position.x,
			itemMesh.position.y,
			itemMesh.position.z + itemWidth / 2 + labelOffset
		);
		scene.add(frontLabel);
	}

	// Back face (Z-)
	var backTexture = createTextTexture(itemCode, itemLength * 10, itemHeight * 10, itemColor);
	if (backTexture) {
		var backGeometry = new THREE.PlaneGeometry(itemLength, itemHeight);
		var backMaterial = new THREE.MeshBasicMaterial({
			map: backTexture,
			transparent: true,
			side: THREE.DoubleSide
		});
		var backLabel = new THREE.Mesh(backGeometry, backMaterial);
		backLabel.position.set(
			itemMesh.position.x,
			itemMesh.position.y,
			itemMesh.position.z - itemWidth / 2 - labelOffset
		);
		backLabel.rotation.y = Math.PI;
		scene.add(backLabel);
	}

	// Right face (X+)
	var rightTexture = createTextTexture(itemCode, itemWidth * 10, itemHeight * 10, itemColor);
	if (rightTexture) {
		var rightGeometry = new THREE.PlaneGeometry(itemWidth, itemHeight);
		var rightMaterial = new THREE.MeshBasicMaterial({
			map: rightTexture,
			transparent: true,
			side: THREE.DoubleSide
		});
		var rightLabel = new THREE.Mesh(rightGeometry, rightMaterial);
		rightLabel.position.set(
			itemMesh.position.x + itemLength / 2 + labelOffset,
			itemMesh.position.y,
			itemMesh.position.z
		);
		rightLabel.rotation.y = Math.PI / 2;
		scene.add(rightLabel);
	}

	// Left face (X-)
	var leftTexture = createTextTexture(itemCode, itemWidth * 10, itemHeight * 10, itemColor);
	if (leftTexture) {
		var leftGeometry = new THREE.PlaneGeometry(itemWidth, itemHeight);
		var leftMaterial = new THREE.MeshBasicMaterial({
			map: leftTexture,
			transparent: true,
			side: THREE.DoubleSide
		});
		var leftLabel = new THREE.Mesh(leftGeometry, leftMaterial);
		leftLabel.position.set(
			itemMesh.position.x - itemLength / 2 - labelOffset,
			itemMesh.position.y,
			itemMesh.position.z
		);
		leftLabel.rotation.y = -Math.PI / 2;
		scene.add(leftLabel);
	}

	// Top face (Y+)
	var topTexture = createTextTexture(itemCode, itemLength * 10, itemWidth * 10, itemColor);
	if (topTexture) {
		var topGeometry = new THREE.PlaneGeometry(itemLength, itemWidth);
		var topMaterial = new THREE.MeshBasicMaterial({
			map: topTexture,
			transparent: true,
			side: THREE.DoubleSide
		});
		var topLabel = new THREE.Mesh(topGeometry, topMaterial);
		topLabel.position.set(
			itemMesh.position.x,
			itemMesh.position.y + itemHeight / 2 + labelOffset,
			itemMesh.position.z
		);
		topLabel.rotation.x = -Math.PI / 2;
		scene.add(topLabel);
	}

	// Bottom face (Y-)
	var bottomTexture = createTextTexture(itemCode, itemLength * 10, itemWidth * 10, itemColor);
	if (bottomTexture) {
		var bottomGeometry = new THREE.PlaneGeometry(itemLength, itemWidth);
		var bottomMaterial = new THREE.MeshBasicMaterial({
			map: bottomTexture,
			transparent: true,
			side: THREE.DoubleSide
		});
		var bottomLabel = new THREE.Mesh(bottomGeometry, bottomMaterial);
		bottomLabel.position.set(
			itemMesh.position.x,
			itemMesh.position.y - itemHeight / 2 - labelOffset,
			itemMesh.position.z
		);
		bottomLabel.rotation.x = Math.PI / 2;
		scene.add(bottomLabel);
	}
}

// Helper function to create text texture for item labels
function createTextTexture(text, width, height, itemColor) {
	var canvas = document.createElement('canvas');
	var context = canvas.getContext('2d');
	if (!context) return null;

	var scale = 4;
	canvas.width = width * scale;
	canvas.height = height * scale;

	// Transparent background
	context.clearRect(0, 0, canvas.width, canvas.height);

	// Draw text with contrasting color
	context.fillStyle = getContrastingColor(itemColor);
	context.textAlign = 'center';
	context.textBaseline = 'middle';

	var fontSize = Math.min(canvas.width, canvas.height) * 0.2;
	context.font = 'bold ' + fontSize + 'px Arial';

	context.fillText(text, canvas.width / 2, canvas.height / 2);

	return new THREE.CanvasTexture(canvas);
}

// Helper function to calculate contrasting color for text
function getContrastingColor(color) {
	var r = color.r;
	var g = color.g;
	var b = color.b;
	var luminance = 0.299 * r + 0.587 * g + 0.114 * b;
	return luminance > 0.5 ? '#000000' : '#FFFFFF';
}

// Helper function to add text labels
function addTextLabel(scene, text, x, y, z) {
	// Create canvas for text
	var canvas = document.createElement('canvas');
	var context = canvas.getContext('2d');
	canvas.width = 256;
	canvas.height = 64;

	context.fillStyle = '#ffffff';
	context.fillRect(0, 0, canvas.width, canvas.height);
	context.font = 'Bold 20px Arial';
	context.fillStyle = '#000000';
	context.textAlign = 'center';
	context.fillText(text, canvas.width / 2, canvas.height / 2 + 7);

	// Create texture from canvas
	var texture = new THREE.CanvasTexture(canvas);
	var material = new THREE.SpriteMaterial({ map: texture });
	var sprite = new THREE.Sprite(material);
	sprite.position.set(x, y, z);
	sprite.scale.set(40, 10, 1);
	scene.add(sprite);
}

function render2DVisualization(container, data) {
	container.html('<canvas id="blueprint-canvas" style="width: 100%; height: 500px; border: 1px solid #ddd;"></canvas>');

	var canvas = container.find('#blueprint-canvas')[0];
	var ctx = canvas.getContext('2d');

	// Set canvas size
	canvas.width = 900;
	canvas.height = 500;

	// Detect dark mode
	var isDarkMode = document.body.classList.contains('dark') ||
	document.documentElement.getAttribute('data-theme') === 'dark';

	// Color scheme based on dark mode
	var colors = {
		background: isDarkMode ? '#1a1a1a' : '#ffffff',
		text: isDarkMode ? '#e0e0e0' : '#333333',
		textSecondary: isDarkMode ? '#b0b0b0' : '#666666',
		border: isDarkMode ? '#404040' : '#333333',
		cartonOutline: isDarkMode ? '#e0e0e0' : '#000000'
	};

	// Clear canvas with theme-appropriate background
	ctx.fillStyle = colors.background;
	ctx.fillRect(0, 0, 900, 500);

	if (!data || !data.carton) {
		ctx.fillStyle = colors.textSecondary;
		ctx.font = '16px Arial';
		ctx.textAlign = 'center';
		ctx.fillText('No carton data available', 450, 250);
		return;
	}

	var carton = data.carton;
	var items = data.item_info || {};
	// Handle pattern-based data structure (Frappe API returns patterns array)
	var positions = {};
	if (data.patterns && data.patterns.length > 0) {
		// Get positions from first pattern
		positions = data.patterns[0].positions_3d || {};
		// Parse if it's a string
		if (typeof positions === 'string') {
			try {
				positions = JSON.parse(positions);
			} catch (e) {
				console.error('Failed to parse positions_3d:', e);
				positions = {};
			}
		}
	} else {
		// Fallback to direct positions_3d if available (backward compatibility)
		positions = data.positions_3d || {};
	}

	// Define view areas with proper spacing
	var topView = { x: 50, y: 60, w: 240, h: 180 };
	var frontView = { x: 330, y: 60, w: 240, h: 180 };
	var sideView = { x: 610, y: 60, w: 240, h: 180 };
	// Calculate unified global scale factor for all views
	// This ensures all three views maintain correct relative proportions
	var padding = 1; // Extra padding within each view

	// Calculate potential scales for each view
	var topScaleW = (topView.w - 2 * padding) / carton.length;
	var topScaleH = (topView.h - 2 * padding) / carton.width;
	var topScale = Math.min(topScaleW, topScaleH);

	var frontScaleW = (frontView.w - 2 * padding) / carton.length;
	var frontScaleH = (frontView.h - 2 * padding) / carton.height;
	var frontScale = Math.min(frontScaleW, frontScaleH);

	var sideScaleW = (sideView.w - 2 * padding) / carton.width;
	var sideScaleH = (sideView.h - 2 * padding) / carton.height;
	var sideScale = Math.min(sideScaleW, sideScaleH);

	// Use the minimum scale across all views to maintain proportions
	var globalScale = Math.min(topScale, frontScale, sideScale);

	// Helper to draw view boundaries and labels
	function drawViewFrame(view, title) {
		ctx.strokeStyle = colors.border;
		ctx.lineWidth = 2;
		ctx.setLineDash([]);
		ctx.strokeRect(view.x, view.y, view.w, view.h);

		ctx.fillStyle = colors.text;
		ctx.font = 'bold 14px Arial';
		ctx.textAlign = 'center';
		ctx.fillText(title, view.x + view.w / 2, view.y - 10);
	}

	// Draw TOP VIEW (X-Y plane) - looking down from above
	function drawTopView() {
		drawViewFrame(topView, 'TOP VIEW');

		// Use global scale to maintain proportions across all views
		var scale = globalScale;

		var cartonDisplayW = carton.length * scale;
		var cartonDisplayH = carton.width * scale;
		var offsetX = topView.x + (topView.w - cartonDisplayW) / 2;
		var offsetY = topView.y + (topView.h - cartonDisplayH) / 2;

		// Draw carton outline
		ctx.strokeStyle = colors.cartonOutline;
		ctx.lineWidth = 2;
		ctx.strokeRect(offsetX, offsetY, cartonDisplayW, cartonDisplayH);

		// Draw items from top view (X-Y plane)
		Object.keys(positions).forEach(function(itemCode) {
			var itemPositions = positions[itemCode];
			var itemInfo = items[itemCode];

			if (!itemPositions || !itemInfo) return;

			ctx.fillStyle = itemInfo.color || '#3498db';

			itemPositions.forEach(function(pos) {
				// Top view: show length × width (X-Y plane)
				// Use rotated dimensions from position if available
				var itemLength = pos.length || itemInfo.length;
				var itemWidth = pos.width || itemInfo.width;
				var itemX = offsetX + pos.x * scale;
				var itemY = offsetY + pos.y * scale;
				var itemW = itemLength * scale;
				var itemH = itemWidth * scale;

				ctx.fillRect(itemX, itemY, itemW, itemH);

				// Label
				ctx.fillStyle = '#ffffff';
				ctx.font = '9px Arial';
				ctx.textAlign = 'center';
				ctx.fillText(itemInfo.name.slice(0, 4), itemX + itemW / 2, itemY + itemH / 2 + 3);
				ctx.fillStyle = itemInfo.color || '#3498db';
			});
		});
	}

	// Draw FRONT VIEW (X-Z plane) - looking from the front
	function drawFrontView() {
		drawViewFrame(frontView, 'FRONT VIEW');

		// Use global scale to maintain proportions across all views
		var scale = globalScale;

		var cartonDisplayW = carton.length * scale;
		var cartonDisplayH = carton.height * scale;
		var offsetX = frontView.x + (frontView.w - cartonDisplayW) / 2;
		var offsetY = frontView.y + (frontView.h - cartonDisplayH) / 2;

		// Draw carton outline
		ctx.strokeStyle = colors.cartonOutline;
		ctx.lineWidth = 2;
		ctx.strokeRect(offsetX, offsetY, cartonDisplayW, cartonDisplayH);

		// Draw items from front view (X-Z plane)
		Object.keys(positions).forEach(function(itemCode) {
			var itemPositions = positions[itemCode];
			var itemInfo = items[itemCode];

			if (!itemPositions || !itemInfo) return;

			ctx.fillStyle = itemInfo.color || '#3498db';

			itemPositions.forEach(function(pos) {
				// Front view: show length × height (X-Z plane)
				// Use rotated dimensions from position if available
				var itemLength = pos.length || itemInfo.length;
				var itemHeight = pos.height || itemInfo.height;
				var itemX = offsetX + pos.x * scale;
				// Flip Y coordinate: (cartonHeight - z - itemHeight) for proper orientation
				var itemY = offsetY + (carton.height - pos.z - itemHeight) * scale;
				var itemW = itemLength * scale;
				var itemH = itemHeight * scale;

				ctx.fillRect(itemX, itemY, itemW, itemH);

				// Label
				ctx.fillStyle = '#ffffff';
				ctx.font = '9px Arial';
				ctx.textAlign = 'center';
				ctx.fillText(itemInfo.name.slice(0, 4), itemX + itemW / 2, itemY + itemH / 2 + 3);
				ctx.fillStyle = itemInfo.color || '#3498db';
			});
		});
	}

	// Draw SIDE VIEW (Y-Z plane) - looking from the side
	function drawSideView() {
		drawViewFrame(sideView, 'SIDE VIEW');

		// Use global scale to maintain proportions across all views
		var scale = globalScale;

		var cartonDisplayW = carton.width * scale;
		var cartonDisplayH = carton.height * scale;
		var offsetX = sideView.x + (sideView.w - cartonDisplayW) / 2;
		var offsetY = sideView.y + (sideView.h - cartonDisplayH) / 2;

		// Draw carton outline
		ctx.strokeStyle = colors.cartonOutline;
		ctx.lineWidth = 2;
		ctx.strokeRect(offsetX, offsetY, cartonDisplayW, cartonDisplayH);

		// Draw items from side view (Y-Z plane)
		Object.keys(positions).forEach(function(itemCode) {
			var itemPositions = positions[itemCode];
			var itemInfo = items[itemCode];

			if (!itemPositions || !itemInfo) return;

			ctx.fillStyle = itemInfo.color || '#3498db';

			itemPositions.forEach(function(pos) {
				// Side view: show width × height (Y-Z plane)
				// Use rotated dimensions from position if available
				var itemWidth = pos.width || itemInfo.width;
				var itemHeight = pos.height || itemInfo.height;
				var itemX = offsetX + pos.y * scale;
				// Flip Y coordinate: (cartonHeight - z - itemHeight) for proper orientation
				var itemY = offsetY + (carton.height - pos.z - itemHeight) * scale;
				var itemW = itemWidth * scale;
				var itemH = itemHeight * scale;

				ctx.fillRect(itemX, itemY, itemW, itemH);

				// Label
				ctx.fillStyle = '#ffffff';
				ctx.font = '9px Arial';
				ctx.textAlign = 'center';
				ctx.fillText(itemInfo.name.slice(0, 4), itemX + itemW / 2, itemY + itemH / 2 + 3);
				ctx.fillStyle = itemInfo.color || '#3498db';
			});
		});
	}

	// Draw info panel
	function drawInfo() {
		ctx.fillStyle = colors.text;
		ctx.font = 'bold 16px Arial';
		ctx.textAlign = 'center';
		ctx.fillText(carton.carton_name + ' - Item Arrangement Views', 450, 25);

		ctx.font = '12px Arial';
		ctx.textAlign = 'left';
		var infoY = 280;
		ctx.fillText('Carton Dimensions: ' + carton.length + ' × ' + carton.width + ' × ' + carton.height + ' cm (L×W×H)', 50, infoY);
		ctx.fillText('Volume: ' + carton.volume + ' cm³', 50, infoY + 20);

		// Items legend
		ctx.fillText('Items:', 450, infoY);
		var legendY = infoY + 20;
		Object.keys(items).forEach(function(itemCode) {
			var item = items[itemCode];
			var count = positions[itemCode] ? positions[itemCode].length : 0;

			ctx.fillStyle = item.color || '#3498db';
			ctx.fillRect(450, legendY - 10, 15, 10);
			ctx.fillStyle = colors.text;
			ctx.fillText(item.name + ' (' + item.length + '×' + item.width + '×' + item.height + 'cm) ×' + count, 470, legendY);
			legendY += 20;
		});
	}

	// Generate all views
	drawTopView();
	drawFrontView();
	drawSideView();
	drawInfo();
}
