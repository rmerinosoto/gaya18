# Guía Rápida - Gaya18

Comandos y operaciones comunes para trabajar con este repositorio.

## 🚀 Inicio Rápido

### Clonar y Configurar

```bash
# Clonar el repositorio con submodules
git clone --recurse-submodules https://github.com/rmerinosoto/gaya18.git
cd gaya18

# Instalar dependencias Python
pip install -r requirements.txt

# Editar configuración
nano odoo.conf
# Actualizar: addons_path, db_name, db_user, db_password
```

### Iniciar Odoo

```bash
# Modo desarrollo
/opt/odoo/odoo-bin -c odoo.conf

# Con actualización de módulos
/opt/odoo/odoo-bin -c odoo.conf -u all -d gaya18
```

## 📦 Gestión de Módulos

### Agregar Módulo de Terceros (Submodule)

```bash
# Desde OCA
git submodule add -b 18.0 https://github.com/OCA/web.git third_party_addons/oca-web
git commit -am "Agregar OCA web modules"
git push

# Después, actualizar lista en Odoo (Apps → Update Apps List)
```

### Crear Módulo Personalizado

```bash
cd custom_addons
mkdir mi_modulo
cd mi_modulo

# Crear estructura básica
touch __init__.py
touch __manifest__.py
mkdir models views security

# Ver custom_addons/README.md para estructura completa
```

### Instalar Módulo

```bash
# Opción 1: Línea de comandos
/opt/odoo/odoo-bin -c odoo.conf -i mi_modulo -d gaya18

# Opción 2: Interfaz web
# Apps → Buscar → Instalar
```

### Actualizar Módulo

```bash
# Actualizar módulo específico
/opt/odoo/odoo-bin -c odoo.conf -u mi_modulo -d gaya18 --stop-after-init

# Actualizar todos
/opt/odoo/odoo-bin -c odoo.conf -u all -d gaya18 --stop-after-init
```

## 🔄 Actualizar Repositorio

### Pull Cambios

```bash
cd /ruta/a/gaya18
git pull origin main

# Actualizar submodules
git submodule update --remote --merge

# Instalar nuevas dependencias
pip install -r requirements.txt

# Reiniciar Odoo
sudo systemctl restart odoo  # Si usa systemd
```

### Actualizar Submódulo Específico

```bash
cd third_party_addons/oca-web
git pull origin 18.0
cd ../..
git add third_party_addons/oca-web
git commit -m "Actualizar oca-web"
git push
```

## 🔍 Depuración

### Ver Logs

```bash
# Si usa systemd
sudo journalctl -u odoo -f

# Si usa archivo de log
tail -f /var/log/odoo/odoo.log

# Logs con más detalle
# Editar odoo.conf: log_level = debug
```

### Modo Debug en Interfaz

```bash
# URL: http://tu-servidor:8069/web?debug=1
# O: Activar desde configuración → Activar modo desarrollador
```

### Shell Interactivo de Odoo

```bash
/opt/odoo/odoo-bin shell -c odoo.conf -d gaya18

# Ejemplo de comandos:
# >>> self.env['res.partner'].search([])
# >>> self.env['mi.modelo'].browse(1)
```

## 🗄️ Base de Datos

### Backup

```bash
# Backup PostgreSQL
pg_dump -U odoo -F c -b -v -f gaya18_backup.dump gaya18

# Backup filestore
tar -czf filestore_backup.tar.gz ~/.local/share/Odoo/filestore/gaya18
```

### Restore

```bash
# Restaurar PostgreSQL
pg_restore -U odoo -d gaya18_nueva -v gaya18_backup.dump

# Restaurar filestore
tar -xzf filestore_backup.tar.gz -C ~/
```

### Crear Nueva Base de Datos

```bash
# Desde interfaz web
# http://localhost:8069/web/database/manager

# O línea de comandos
/opt/odoo/odoo-bin -c odoo.conf -d nueva_bd --init=base --stop-after-init
```

## 🔧 Mantenimiento

### Limpiar Cache

```bash
# Limpiar archivos .pyc
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +

# Reiniciar Odoo
sudo systemctl restart odoo
```

### Verificar Addons Path

```bash
cat odoo.conf | grep addons_path

# Verificar que los directorios existan
ls -la custom_addons/
ls -la third_party_addons/
```

### Actualizar Dependencias

```bash
# Actualizar requirements.txt
pip install -r requirements.txt --upgrade

# Verificar versiones instaladas
pip list | grep odoo
```

## 🚨 Troubleshooting

### Módulo No Aparece

```bash
# 1. Verificar que el módulo esté en addons_path
ls -la custom_addons/mi_modulo/

# 2. Verificar __manifest__.py
cat custom_addons/mi_modulo/__manifest__.py

# 3. Actualizar lista de aplicaciones
/opt/odoo/odoo-bin -c odoo.conf -u base -d gaya18 --stop-after-init

# 4. Reiniciar Odoo
sudo systemctl restart odoo
```

### Error de Dependencias

```bash
# Ver error completo en logs
sudo journalctl -u odoo -n 100

# Instalar dependencia faltante
pip install nombre_paquete

# Actualizar requirements.txt
echo "nombre_paquete==version" >> requirements.txt
```

### Error de Permisos

```bash
# Dar permisos al usuario odoo
sudo chown -R odoo:odoo /ruta/a/gaya18

# Verificar permisos
ls -la /ruta/a/gaya18
```

## 📊 Comandos Útiles Git

```bash
# Ver estado
git status

# Ver cambios
git diff

# Ver historial
git log --oneline -10

# Descartar cambios locales
git checkout -- archivo.py

# Ver submódulos
git submodule status

# Actualizar todos los submódulos
git submodule update --remote --merge
```

## 🔐 Seguridad

### Cambiar Admin Password

```bash
# Editar odoo.conf
nano odoo.conf
# Cambiar: admin_passwd = tu_contraseña_segura

# Reiniciar
sudo systemctl restart odoo
```

### Configurar Modo Proxy

```bash
# Si usas Nginx/Apache como proxy
nano odoo.conf
# Descomentar: proxy_mode = True
# Descomentar: list_db = False
```

## 📚 Recursos

- **README.md**: Documentación completa del repositorio
- **DEPLOYMENT.md**: Guía de despliegue en servidor SSH
- **custom_addons/README.md**: Guía para crear módulos personalizados
- **third_party_addons/README.md**: Guía para gestionar módulos de terceros

## 💡 Tips

1. **Siempre prueba en desarrollo** antes de actualizar producción
2. **Haz backup** antes de actualizaciones importantes
3. **Usa git submodules** para módulos de terceros
4. **Documenta tus cambios** en commits claros
5. **Revisa logs** regularmente para detectar problemas
6. **Mantén actualizado** requirements.txt con dependencias

## 🆘 Obtener Ayuda

- Issues: https://github.com/rmerinosoto/gaya18/issues
- Documentación Odoo: https://www.odoo.com/documentation/18.0/
- OCA: https://github.com/OCA

---

Para detalles completos, consulta README.md y DEPLOYMENT.md
