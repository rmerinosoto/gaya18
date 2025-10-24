# Example Module

This is a template module for creating custom addons in Gaya18.

## Features

- Basic model with common field types
- Tree, form, and search views
- State workflow (draft → confirmed → done)
- Computed fields
- Constraints validation
- Menu items
- Access rights

## Installation

1. Ensure the module is in `custom_addons/` directory
2. Restart Odoo server
3. Update Apps List (Apps → Update Apps List)
4. Search for "Example Module"
5. Click Install

## Usage

After installation, you'll find a new menu "Example" in the main menu bar.

### Create a Record

1. Go to Example → Example Records
2. Click Create
3. Fill in the required fields
4. Save

### Workflow

- **Draft**: Initial state
- **Confirm**: Validate and confirm the record
- **Done**: Mark as completed
- **Cancel**: Cancel the record (can reset to draft)

## Customization

### To create your own module based on this template:

1. Copy this folder and rename it
2. Update `__manifest__.py`:
   - Change `name`, `summary`, `description`
   - Update `author`, `website`
3. Rename model files and classes
4. Update model name in views XML
5. Customize fields and business logic
6. Update security rules
7. Test thoroughly before deploying

### File Structure

```
example_module/
├── __init__.py              # Module initialization
├── __manifest__.py          # Module metadata
├── models/
│   ├── __init__.py         # Models initialization
│   └── example_model.py    # Main model
├── views/
│   ├── example_views.xml   # Views definition
│   └── menu_views.xml      # Menu items
├── security/
│   └── ir.model.access.csv # Access rights
└── static/
    └── description/
        ├── icon.png        # Module icon
        └── index.html      # Module description page
```

## Development Tips

- Use `self.ensure_one()` for methods that work on a single record
- Always validate user input
- Use computed fields for derived values
- Follow Odoo naming conventions
- Test with different user permissions
- Document your code

## References

- [Odoo 18 Developer Documentation](https://www.odoo.com/documentation/18.0/developer.html)
- [ORM API Reference](https://www.odoo.com/documentation/18.0/developer/reference/backend/orm.html)
- [Views Reference](https://www.odoo.com/documentation/18.0/developer/reference/backend/views.html)

---

**Note**: This is a template module for demonstration purposes. Customize it according to your specific requirements.
