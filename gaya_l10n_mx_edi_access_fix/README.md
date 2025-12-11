# Gaya - Fix Global Invoice Access

## Problem

Users with the Invoicing group (`account.group_account_invoice`) but without Settings permission (`base.group_system`) were unable to create Global Invoices from the POS module. They received the error:

```
Lo sentimos, no tiene permiso para acceder a este documento.
```

This prevented accountants from performing their normal duties without requiring full admin/Settings access.

## Solution

This module overrides the `action_create_global_invoice()` method in the `l10n_mx_edi.global_invoice.create` wizard to execute with `sudo()` privileges. This bypasses the permission checks while maintaining security through Odoo's standard group-based access to the POS and Invoicing modules.

### Key Implementation Details

1. **Python Override**: Inherits `l10n_mx_edi.global_invoice.create` and wraps the parent method call with `sudo()`
2. **Dependency Order**: Depends on `l10n_mx_edi_pos` to ensure proper Method Resolution Order (MRO)
3. **Minimal Logging**: Logs user information when creating global invoices for audit purposes

## Technical Details

- **Model**: `l10n_mx_edi.global_invoice.create` (TransientModel)
- **Method**: `action_create_global_invoice()`
- **Approach**: `super(ClassName, self.sudo()).action_create_global_invoice()`
- **Dependencies**: Must load after `l10n_mx_edi_pos` to be first in the MRO chain

## Installation

1. Copy this module to your custom addons directory
2. Update apps list
3. Install the module
4. Users with Invoicing group can now create global invoices from POS

## Version History

### 18.0.1.0.15 (Final Clean Version)
- Removed unnecessary ACL rules and record rules
- Simplified code to only the essential sudo() override
- Cleaned up logging to be minimal and informative
- Updated documentation to reflect actual solution

### 18.0.1.0.14
- Added `l10n_mx_edi_pos` to dependencies
- Fixed MRO issue - override now executes correctly
- **Solution confirmed working**

### 18.0.1.0.12-1.0.13
- Implemented Python override with sudo()
- Added detailed error logging

### 18.0.1.0.11
- Added record rule for account.journal access

### 18.0.1.0.9-1.0.10
- Initial attempts with ACL rules (not sufficient)

## License

LGPL-3
