# Gaya18 - Odoo v18 Third-Party Addons Repository

Este repositorio gestiona los módulos y aplicaciones de terceros para la base de datos **gaya18** de Odoo v18.

## 📁 Estructura del Repositorio

```
gaya18/
├── custom_addons/          # Módulos personalizados desarrollados internamente
├── third_party_addons/     # Módulos de terceros (OCA, Odoo Store, etc.)
├── odoo.conf              # Archivo de configuración de Odoo
├── requirements.txt       # Dependencias Python adicionales
└── README.md             # Este archivo
```

## 🚀 Configuración Inicial

### 1. Clonar el Repositorio

```bash
git clone https://github.com/rmerinosoto/gaya18.git
cd gaya18
```

### 2. Configurar Odoo

Edita el archivo `odoo.conf` y actualiza las siguientes rutas:

```ini
addons_path = /ruta/a/odoo/addons,/ruta/a/gaya18/custom_addons,/ruta/a/gaya18/third_party_addons
db_name = gaya18
db_user = tu_usuario
db_password = tu_contraseña
```

### 3. Instalar Dependencias Python

```bash
pip install -r requirements.txt
```

## 📦 Agregar Módulos de Terceros

### Opción 1: Agregar Módulos Directamente

Copia el módulo directamente en la carpeta correspondiente:

```bash
# Para módulos de terceros
cp -r /ruta/al/modulo third_party_addons/

# Para módulos personalizados
cp -r /ruta/al/modulo custom_addons/
```

### Opción 2: Usar Git Submodules (Recomendado)

Esta es la forma recomendada para gestionar módulos externos, ya que facilita las actualizaciones:

```bash
# Agregar un submodule
git submodule add -b 18.0 https://github.com/OCA/nombre-repo.git third_party_addons/nombre-repo

# Commit y push
git commit -am "Agregar módulo nombre-repo como submodule"
git push
```

Para clonar el repositorio incluyendo los submodules:

```bash
git clone --recurse-submodules https://github.com/rmerinosoto/gaya18.git
```

O si ya tienes el repositorio clonado:

```bash
git submodule update --init --recursive
```

## 🔄 Actualizar Submódulos

Para actualizar todos los submódulos a su última versión:

```bash
git submodule update --remote --merge
git commit -am "Actualizar submódulos"
git push
```

## 🏃 Ejecutar Odoo

### Desde el Servidor SSH

```bash
# Usando el archivo de configuración
./odoo-bin -c /ruta/a/gaya18/odoo.conf

# O especificando los addons directamente
./odoo-bin --addons-path=/ruta/a/odoo/addons,/ruta/a/gaya18/custom_addons,/ruta/a/gaya18/third_party_addons -d gaya18
```

### Actualizar Lista de Módulos

Después de agregar nuevos módulos:

```bash
./odoo-bin -c /ruta/a/gaya18/odoo.conf -u all -d gaya18 --stop-after-init
```

O desde la interfaz web:
1. Activar el modo desarrollador
2. Ir a Aplicaciones
3. Actualizar lista de aplicaciones

## 📋 Mejores Prácticas

1. **Organización**: Mantén separados los módulos personalizados de los de terceros
2. **Submodules**: Usa git submodules para módulos externos, facilita actualizaciones
3. **Versiones**: Ancla los submodules a versiones específicas (tags o commits) para evitar cambios inesperados
4. **Documentación**: Documenta las dependencias y configuraciones especiales de cada módulo
5. **Testing**: Prueba siempre en un entorno de desarrollo antes de actualizar en producción

## 🔒 Seguridad

- **IMPORTANTE**: No commits contraseñas reales en `odoo.conf`
- Usa variables de entorno o archivos de configuración separados para datos sensibles
- En producción, configura `admin_passwd` con una contraseña fuerte

## 📚 Recursos Útiles

- [Documentación Oficial Odoo 18](https://www.odoo.com/documentation/18.0/)
- [Odoo Community Association (OCA)](https://github.com/OCA)
- [Odoo.sh Documentation](https://www.odoo.com/documentation/18.0/administration/odoo_sh.html)

## 🤝 Contribuir

Para agregar un nuevo módulo:

1. Crea una rama: `git checkout -b feature/nuevo-modulo`
2. Agrega el módulo en la carpeta correspondiente
3. Actualiza `requirements.txt` si es necesario
4. Commit y push: `git push origin feature/nuevo-modulo`
5. Crea un Pull Request

## 📞 Soporte

Para preguntas o problemas, abre un issue en este repositorio.

---

**Versión Odoo**: 18.0  
**Base de Datos**: gaya18  
**Mantenedor**: rmerinosoto