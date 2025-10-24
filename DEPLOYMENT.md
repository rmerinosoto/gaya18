# Guía de Despliegue en Servidor SSH

Esta guía te ayudará a desplegar el repositorio gaya18 en tu servidor SSH con Odoo v18.

## Requisitos Previos

- Servidor con acceso SSH
- Odoo 18 instalado en el servidor
- PostgreSQL instalado y configurado
- Python 3.10 o superior
- Git instalado en el servidor

## Configuración Inicial en el Servidor

### 1. Conectar al Servidor SSH

```bash
ssh usuario@tu-servidor.com
```

### 2. Navegar al Directorio de Odoo

```bash
cd /opt/odoo  # O la ruta donde está instalado Odoo
```

### 3. Clonar el Repositorio

```bash
# Clonar sin submodules
git clone https://github.com/rmerinosoto/gaya18.git

# O clonar con submodules
git clone --recurse-submodules https://github.com/rmerinosoto/gaya18.git

cd gaya18
```

### 4. Configurar Git Credentials (si es necesario)

Para repositorios privados o submodules privados:

```bash
# Opción 1: Configurar SSH Key
ssh-keygen -t ed25519 -C "tu_email@example.com"
cat ~/.ssh/id_ed25519.pub
# Agregar la clave pública a GitHub

# Opción 2: Usar credential helper
git config --global credential.helper store
```

### 5. Instalar Dependencias Python

```bash
# Activar el entorno virtual de Odoo si existe
source /opt/odoo/venv/bin/activate

# Instalar dependencias del repositorio
pip install -r requirements.txt
```

### 6. Configurar odoo.conf

```bash
# Editar el archivo de configuración
nano odoo.conf

# Actualizar las rutas absolutas
# addons_path = /opt/odoo/odoo/addons,/opt/odoo/gaya18/custom_addons,/opt/odoo/gaya18/third_party_addons

# Configurar la base de datos
# db_name = gaya18
# db_user = odoo
# db_password = tu_contraseña_segura

# Guardar y salir (Ctrl+X, Y, Enter)
```

### 7. Crear la Base de Datos (si no existe)

```bash
# Conectar a PostgreSQL
sudo -u postgres psql

# Crear usuario y base de datos
CREATE USER odoo WITH PASSWORD 'tu_contraseña_segura';
CREATE DATABASE gaya18 OWNER odoo;
\q
```

### 8. Iniciar Odoo

```bash
# Opción 1: Modo desarrollo
/opt/odoo/odoo-bin -c /opt/odoo/gaya18/odoo.conf

# Opción 2: Como servicio (ver sección siguiente)
sudo systemctl start odoo
```

## Configurar Odoo como Servicio Systemd

### 1. Crear Archivo de Servicio

```bash
sudo nano /etc/systemd/system/odoo.service
```

### 2. Contenido del Archivo

```ini
[Unit]
Description=Odoo 18
Documentation=https://www.odoo.com/documentation/18.0
After=network.target postgresql.service

[Service]
Type=simple
User=odoo
Group=odoo
ExecStart=/opt/odoo/venv/bin/python3 /opt/odoo/odoo-bin -c /opt/odoo/gaya18/odoo.conf
WorkingDirectory=/opt/odoo
StandardOutput=journal+console

[Install]
WantedBy=multi-user.target
```

### 3. Activar y Ejecutar el Servicio

```bash
# Recargar systemd
sudo systemctl daemon-reload

# Habilitar inicio automático
sudo systemctl enable odoo

# Iniciar servicio
sudo systemctl start odoo

# Ver estado
sudo systemctl status odoo

# Ver logs
sudo journalctl -u odoo -f
```

## Actualizar el Repositorio

### Actualizar Código

```bash
cd /opt/odoo/gaya18

# Pull cambios
git pull origin main

# Actualizar submodules
git submodule update --remote --merge

# Instalar nuevas dependencias
pip install -r requirements.txt

# Reiniciar Odoo
sudo systemctl restart odoo
```

### Actualizar Módulos en Odoo

```bash
# Opción 1: Actualizar todos los módulos
/opt/odoo/odoo-bin -c /opt/odoo/gaya18/odoo.conf -u all -d gaya18 --stop-after-init

# Opción 2: Actualizar módulo específico
/opt/odoo/odoo-bin -c /opt/odoo/gaya18/odoo.conf -u nombre_modulo -d gaya18 --stop-after-init

# Reiniciar servicio
sudo systemctl restart odoo
```

## Configuración de Nginx (Opcional)

Si quieres usar Nginx como proxy reverso:

### 1. Instalar Nginx

```bash
sudo apt update
sudo apt install nginx
```

### 2. Configurar Virtual Host

```bash
sudo nano /etc/nginx/sites-available/odoo
```

```nginx
upstream odoo {
    server 127.0.0.1:8069;
}

upstream odoochat {
    server 127.0.0.1:8072;
}

server {
    listen 80;
    server_name tu-dominio.com;

    access_log /var/log/nginx/odoo-access.log;
    error_log /var/log/nginx/odoo-error.log;

    proxy_read_timeout 720s;
    proxy_connect_timeout 720s;
    proxy_send_timeout 720s;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Real-IP $remote_addr;

    location / {
        proxy_redirect off;
        proxy_pass http://odoo;
    }

    location /longpolling {
        proxy_pass http://odoochat;
    }

    location ~* /web/static/ {
        proxy_cache_valid 200 90m;
        proxy_buffering on;
        expires 864000;
        proxy_pass http://odoo;
    }

    gzip on;
    gzip_types text/css text/less text/plain text/xml application/xml application/json application/javascript;
}
```

### 3. Activar Configuración

```bash
sudo ln -s /etc/nginx/sites-available/odoo /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 4. Configurar SSL con Let's Encrypt (Recomendado)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d tu-dominio.com
```

## Configuración de Seguridad

### 1. Configurar Firewall

```bash
# UFW
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# O iptables
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
```

### 2. Configurar PostgreSQL

```bash
# Editar pg_hba.conf
sudo nano /etc/postgresql/*/main/pg_hba.conf

# Permitir solo conexiones locales
# local   all             all                                     peer
# host    all             all             127.0.0.1/32            md5
```

### 3. Asegurar odoo.conf

```bash
# Cambiar permisos
sudo chmod 600 /opt/odoo/gaya18/odoo.conf
sudo chown odoo:odoo /opt/odoo/gaya18/odoo.conf
```

## Backup y Restauración

### Backup Base de Datos

```bash
# Crear backup
pg_dump -U odoo -F c -b -v -f /backup/gaya18_$(date +%Y%m%d).backup gaya18

# Programar backup automático con cron
crontab -e
# Agregar: 0 2 * * * pg_dump -U odoo -F c -b -v -f /backup/gaya18_$(date +\%Y\%m\%d).backup gaya18
```

### Restaurar Base de Datos

```bash
# Restaurar backup
pg_restore -U odoo -d gaya18 -v /backup/gaya18_20250124.backup
```

### Backup Filestore

```bash
# Backup
tar -czf /backup/filestore_$(date +%Y%m%d).tar.gz /opt/odoo/.local/share/Odoo/filestore/gaya18

# Restaurar
tar -xzf /backup/filestore_20250124.tar.gz -C /
```

## Monitoreo

### Ver Logs en Tiempo Real

```bash
# Logs de Odoo (si usa systemd)
sudo journalctl -u odoo -f

# Logs de archivo
tail -f /var/log/odoo/odoo.log

# Logs de Nginx
tail -f /var/log/nginx/odoo-access.log
tail -f /var/log/nginx/odoo-error.log
```

### Monitorear Recursos

```bash
# CPU y RAM
htop

# Espacio en disco
df -h

# Procesos de Odoo
ps aux | grep odoo
```

## Troubleshooting

### Problema: Odoo no inicia

```bash
# Verificar logs
sudo journalctl -u odoo -n 50

# Verificar puertos
sudo netstat -tlnp | grep 8069

# Verificar permisos
ls -la /opt/odoo/gaya18/
```

### Problema: Base de datos no conecta

```bash
# Verificar PostgreSQL está corriendo
sudo systemctl status postgresql

# Verificar usuario y contraseña
sudo -u postgres psql
\du
\l
```

### Problema: Módulos no aparecen

```bash
# Actualizar lista de aplicaciones
/opt/odoo/odoo-bin -c /opt/odoo/gaya18/odoo.conf -u base -d gaya18 --stop-after-init

# Verificar addons_path en odoo.conf
cat /opt/odoo/gaya18/odoo.conf | grep addons_path
```

## Scripts Útiles

### Script de Actualización

Crear `/opt/odoo/gaya18/update.sh`:

```bash
#!/bin/bash
echo "Actualizando gaya18..."
cd /opt/odoo/gaya18
git pull origin main
git submodule update --remote --merge
pip install -r requirements.txt
sudo systemctl restart odoo
echo "Actualización completada!"
```

```bash
chmod +x update.sh
```

### Script de Backup

Crear `/opt/odoo/backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/backup/gaya18"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup base de datos
pg_dump -U odoo -F c -b -v -f $BACKUP_DIR/db_$DATE.backup gaya18

# Backup filestore
tar -czf $BACKUP_DIR/filestore_$DATE.tar.gz /opt/odoo/.local/share/Odoo/filestore/gaya18

# Limpiar backups antiguos (más de 7 días)
find $BACKUP_DIR -type f -mtime +7 -delete

echo "Backup completado: $DATE"
```

```bash
chmod +x backup.sh
# Agregar a cron para ejecutar diariamente
```

## Referencias

- [Guía de Deploy Odoo](https://www.odoo.com/documentation/18.0/administration/on_premise.html)
- [Odoo Performance](https://www.odoo.com/documentation/18.0/administration/on_premise/performance.html)
- [PostgreSQL Backup](https://www.postgresql.org/docs/current/backup.html)

---

Para cualquier problema, consulta los logs o abre un issue en el repositorio.
