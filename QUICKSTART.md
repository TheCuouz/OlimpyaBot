# Quick Start - Iniciar Bot en 5 minutos

## Paso 1: Preparar Entorno

```bash
# Crear entorno virtual
python -m venv venv

# Activar (Windows)
venv\Scripts\activate

# O activar (Linux/Mac)
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

## Paso 2: Configurar Token

1. **Obtener token de Discord**
   - Ir a https://discord.com/developers/applications
   - Click en "New Application"
   - Ir a "Bot" y "Add Bot"
   - Copiar el token

2. **Guardar en .env**
   ```bash
   # Copiar .env.example
   cp .env.example .env
   
   # Editar .env y pegar el token
   DISCORD_TOKEN=tu_token_aqui
   ```

3. **Invitar Bot a Discord**
   - En Developer Portal, ir a "OAuth2" → "URL Generator"
   - Seleccionar scopes: `bot`
   - Seleccionar permisos: `Send Messages`, `Read Messages`
   - Copiar URL generada
   - Abrir en navegador e invitar al servidor

## Paso 3: Ejecutar

```bash
python main.py
```

Deberías ver:
```
2024-XX-XX XX:XX:XX - OlimpyaBot - INFO - El bot está listo y online como BotName#1234
```

## Paso 4: Probar

En Discord, escribe: `Desidia`

El bot responderá: `Que pasa perro?`

## Verificación

✅ Bot conectado a Discord
✅ Bot responde a "Desidia"
✅ Logs guardándose en `logs/`
✅ ¡Listo!

## Troubleshooting Rápido

| Problema | Solución |
|----------|----------|
| ModuleNotFoundError: No module named 'discord' | Ejecutar `pip install -r requirements.txt` |
| ValueError: DISCORD_TOKEN no está configurado | Verificar archivo `.env` tiene token válido |
| Bot no responde | Verificar permisos "Send Messages" en canal |
| ConnectionError | Verificar token y conexión a internet |

## Agregar Más Respuestas Rápido

Editar `config.py`:

```python
RESPONSES = {
    "desidia": "Que pasa perro?",
    "hola": "Hola! ¿Cómo estás?",
    "adiós": "¡Hasta luego!",
}
```

Reiniciar bot (Ctrl+C y python main.py).

## Próximos Pasos

- Leer [ARCHITECTURE.md](ARCHITECTURE.md) para entender estructura
- Crear nuevo Cog para agregar comandos
- Revisar [README.md](README.md) para documentación completa
