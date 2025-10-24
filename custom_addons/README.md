# Custom Addons

Este directorio contiene los módulos personalizados desarrollados específicamente para gaya18.

## Estructura de un Módulo Odoo

Cada módulo debe seguir esta estructura básica:

```
mi_modulo/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── mi_modelo.py
├── views/
│   └── mi_vista.xml
├── security/
│   └── ir.model.access.csv
├── data/
│   └── data.xml
└── static/
    └── description/
        └── icon.png
```

## Crear un Nuevo Módulo

### 1. Estructura Básica

```bash
cd custom_addons
mkdir mi_modulo
cd mi_modulo
```

### 2. Archivo __manifest__.py

```python
{
    'name': 'Mi Módulo',
    'version': '18.0.1.0.0',
    'category': 'Custom',
    'summary': 'Descripción corta del módulo',
    'description': """
        Descripción larga del módulo
        ============================
        * Funcionalidad 1
        * Funcionalidad 2
    """,
    'author': 'Tu Nombre',
    'website': 'https://www.tuwebsite.com',
    'license': 'LGPL-3',
    'depends': ['base'],  # Dependencias de otros módulos
    'data': [
        'security/ir.model.access.csv',
        'views/mi_vista.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
```

### 3. Archivo __init__.py

```python
from . import models
```

### 4. Modelo (models/__init__.py)

```python
from . import mi_modelo
```

### 5. Modelo (models/mi_modelo.py)

```python
from odoo import models, fields, api

class MiModelo(models.Model):
    _name = 'mi.modulo.modelo'
    _description = 'Descripción del Modelo'

    name = fields.Char(string='Nombre', required=True)
    description = fields.Text(string='Descripción')
    active = fields.Boolean(string='Activo', default=True)
```

### 6. Vista (views/mi_vista.xml)

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_mi_modelo_tree" model="ir.ui.view">
        <field name="name">mi.modulo.modelo.tree</field>
        <field name="model">mi.modulo.modelo</field>
        <field name="arch" type="xml">
            <tree>
                <field name="name"/>
                <field name="description"/>
            </tree>
        </field>
    </record>

    <record id="view_mi_modelo_form" model="ir.ui.view">
        <field name="name">mi.modulo.modelo.form</field>
        <field name="model">mi.modulo.modelo</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <group>
                        <field name="name"/>
                        <field name="description"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>

    <record id="action_mi_modelo" model="ir.actions.act_window">
        <field name="name">Mi Modelo</field>
        <field name="res_model">mi.modulo.modelo</field>
        <field name="view_mode">tree,form</field>
    </record>

    <menuitem id="menu_mi_modulo_root"
              name="Mi Módulo"
              sequence="10"/>

    <menuitem id="menu_mi_modelo"
              name="Mi Modelo"
              parent="menu_mi_modulo_root"
              action="action_mi_modelo"
              sequence="10"/>
</odoo>
```

### 7. Seguridad (security/ir.model.access.csv)

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_mi_modelo,access_mi_modelo,model_mi_modulo_modelo,base.group_user,1,1,1,1
```

## Buenas Prácticas

1. **Naming**: Usa nombres descriptivos en snake_case para módulos
2. **Versioning**: Sigue el esquema `18.0.x.y.z` (versión Odoo.major.minor.patch)
3. **Dependencies**: Declara todas las dependencias en `__manifest__.py`
4. **Security**: Siempre define permisos de acceso para tus modelos
5. **Documentation**: Documenta tu código y actualiza el README
6. **Testing**: Prueba tu módulo en un entorno de desarrollo antes de producción

## Comandos Útiles

```bash
# Instalar módulo
./odoo-bin -c odoo.conf -i mi_modulo -d gaya18

# Actualizar módulo
./odoo-bin -c odoo.conf -u mi_modulo -d gaya18

# Desinstalar módulo
./odoo-bin -c odoo.conf --uninstall mi_modulo -d gaya18
```

## Recursos

- [Guía de Desarrollo Odoo 18](https://www.odoo.com/documentation/18.0/developer.html)
- [ORM API](https://www.odoo.com/documentation/18.0/developer/reference/backend/orm.html)
- [Vistas](https://www.odoo.com/documentation/18.0/developer/reference/backend/views.html)
