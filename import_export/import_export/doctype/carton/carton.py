from frappe.utils import flt
from frappe.model.document import Document

class Carton(Document):
    def validate(self):
        self.volume = self.length * self.width * self.height
