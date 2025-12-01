# Gaya - Fix Global Invoice Access

## Descripción

Módulo que permite a usuarios con el grupo **Facturación** usar la acción "Crear factura global" de México sin requerir el permiso de **Ajustes**.

## Problema que resuelve

El método `l10n_mx_edi_action_create_global_invoice()` retorna un diccionario tipo `ir.actions.act_window`. Odoo valida permisos sobre este modelo, que por defecto solo permite acceso a usuarios con grupo "Ajustes".

Error original: "Lo sentimos, no tiene permiso para acceder a este documento."

## Solución

Agrega reglas de acceso de **solo lectura** sobre `ir.actions.act_window` para el grupo Facturación.

## Instalación

1. Ir a **Aplicaciones**
2. **Actualizar lista de aplicaciones**
3. Buscar: `Gaya - Fix Global Invoice Access`
4. Clic en **Instalar**

## Seguridad

- ✅ Solo lectura (no escritura/creación/borrado)
- ✅ Compatible con actualizaciones
- ✅ Reversible

## Versión

1.0.0 - Odoo 18.0

## Licencia

LGPL-3
