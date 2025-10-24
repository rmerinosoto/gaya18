# Third Party Addons

Este directorio contiene módulos de terceros para Odoo v18.

## Fuentes Recomendadas de Módulos

### 1. Odoo Community Association (OCA)
Repositorios de alta calidad mantenidos por la comunidad:
- https://github.com/OCA

Ejemplos de repositorios útiles:
- **web**: Mejoras de interfaz web
- **server-tools**: Herramientas del servidor
- **account-financial-tools**: Herramientas de contabilidad
- **stock-logistics-warehouse**: Gestión de inventario
- **sale-workflow**: Flujo de ventas
- **purchase-workflow**: Flujo de compras

### 2. Odoo Apps Store
- https://apps.odoo.com/apps/modules/browse?version=18.0

### 3. Repositorios Privados
Para módulos propietarios o específicos de la empresa.

## Agregar Módulos con Git Submodules

### Agregar un repositorio OCA completo

```bash
# Ejemplo: Agregar módulos web de OCA
git submodule add -b 18.0 https://github.com/OCA/web.git third_party_addons/oca-web

# Commit
git commit -am "Agregar OCA web modules"
git push
```

### Agregar desde un repositorio privado

```bash
# Usando SSH
git submodule add -b 18.0 git@github.com:empresa/modulo-privado.git third_party_addons/modulo-privado

# Usando HTTPS con token
git submodule add -b 18.0 https://TOKEN@github.com/empresa/modulo-privado.git third_party_addons/modulo-privado
```

## Gestión de Submodules

### Inicializar submodules después de clonar

```bash
git submodule update --init --recursive
```

### Actualizar un submodule específico

```bash
cd third_party_addons/oca-web
git pull origin 18.0
cd ../..
git add third_party_addons/oca-web
git commit -m "Actualizar oca-web a última versión"
git push
```

### Actualizar todos los submodules

```bash
git submodule update --remote --merge
git commit -am "Actualizar todos los submódulos"
git push
```

### Anclar un submodule a un commit específico

```bash
cd third_party_addons/oca-web
git checkout COMMIT_HASH
cd ../..
git add third_party_addons/oca-web
git commit -m "Anclar oca-web a commit específico"
git push
```

### Remover un submodule

```bash
git submodule deinit -f third_party_addons/modulo
git rm -f third_party_addons/modulo
rm -rf .git/modules/third_party_addons/modulo
git commit -m "Remover módulo de terceros"
git push
```

## Agregar Módulos Directamente (Sin Submodules)

Si prefieres no usar submodules:

```bash
# Clonar el repositorio temporalmente
cd /tmp
git clone -b 18.0 https://github.com/OCA/web.git

# Copiar solo el módulo que necesitas
cp -r web/web_responsive /ruta/a/gaya18/third_party_addons/

# Actualizar el repositorio
cd /ruta/a/gaya18
git add third_party_addons/web_responsive
git commit -m "Agregar módulo web_responsive"
git push
```

## Verificar Compatibilidad

Antes de instalar un módulo, verifica:
1. **Versión**: Asegúrate que sea compatible con Odoo 18.0
2. **Dependencias**: Revisa los módulos requeridos en `__manifest__.py`
3. **Dependencias Python**: Revisa si requiere paquetes adicionales
4. **Licencia**: Verifica que la licencia sea compatible con tu uso

## Ejemplo de Estructura

```
third_party_addons/
├── README.md                    # Este archivo
├── oca-web/                     # Submodule de OCA web
│   ├── web_responsive/
│   ├── web_timeline/
│   └── ...
├── oca-server-tools/           # Submodule de OCA server-tools
│   ├── base_technical_user/
│   └── ...
└── custom-vendor-module/       # Módulo de un proveedor específico
    └── __manifest__.py
```

## Actualizar Odoo con Nuevos Módulos

Después de agregar módulos:

```bash
# Reiniciar Odoo y actualizar lista de aplicaciones
./odoo-bin -c odoo.conf -u base -d gaya18 --stop-after-init

# O desde la interfaz web:
# Apps → Update Apps List
```

## Notas Importantes

⚠️ **Advertencia**: No modifiques directamente los archivos dentro de los submodules. Cualquier cambio se perderá al actualizar.

✅ **Recomendación**: Si necesitas personalizar un módulo de terceros:
1. Crea un módulo heredero en `custom_addons/`
2. Usa herencia de modelos y vistas
3. Mantén el módulo original sin modificar

## Recursos

- [OCA Guidelines](https://odoo-community.org/)
- [Git Submodules Documentation](https://git-scm.com/book/en/v2/Git-Tools-Submodules)
- [Odoo Apps](https://apps.odoo.com/)
