# OlimpyaBot - Python Edition

Bot de Discord profesional convertido de Java (JDA) a Python (discord.py).

## Características

- ✅ Estructura modular con Cogs
- ✅ Logging profesional (consola + archivo)
- ✅ Configuración centralizada
- ✅ Manejo robusto de errores
- ✅ Variables de entorno
- ✅ Responde a "Desidia" con "Que pasa perro?"

## Requisitos

- Python 3.8+
- pip

## Instalación

1. **Clonar o descargar el proyecto**

2. **Crear entorno virtual (recomendado)**
   ```bash
   python -m venv venv
   ```

3. **Activar entorno virtual**
   - Windows:
     ```bash
     venv\Scripts\activate
     ```
   - Linux/Mac:
     ```bash
     source venv/bin/activate
     ```

4. **Instalar dependencias**
   ```bash
   pip install -r requirements.txt
   ```

5. **Configurar variables de entorno**
   - Copiar `.env.example` a `.env`
   - Reemplazar `your_bot_token_here` con el token real del bot

6. **Ejecutar el bot**
   ```bash
   python main.py
   ```

## Estructura del Proyecto

```
OlimpyaBot-Python/
├── main.py              # Punto de entrada
├── config.py            # Configuración centralizada
├── requirements.txt     # Dependencias
├── .env.example         # Ejemplo de variables de entorno
├── .gitignore           # Archivos a ignorar en git
├── cogs/                # Módulos funcionales
│   ├── events.py        # Eventos del bot (Ready, Guild Join/Leave)
│   └── messages.py      # Manejador de mensajes
├── utils/               # Utilidades
│   └── logger.py        # Sistema de logging
└── logs/                # Logs del bot
```

## Configuración

### Token de Discord

1. Ir a [Discord Developer Portal](https://discord.com/developers/applications)
2. Crear nueva aplicación
3. Ir a "Bot" y crear bot
4. Copiar el token
5. Pegarlo en `.env` como `DISCORD_TOKEN`

### Permisos del Bot

Asegurar que el bot tenga estos permisos:
- Send Messages
- Read Messages/View Channels
- Read Message History

## Comandos de Ejemplo

El bot responde automáticamente a:
- `Desidia` → "Que pasa perro?"

Fácilmente extensible para agregar más comandos.

## Logging

- **Consola**: Mensajes INFO y superior
- **Archivo**: Todos los mensajes en `logs/bot_*.log`

## Desarrollo

### Agregar nuevo Cog

1. Crear archivo en `cogs/`
2. Implementar clase que herede de `commands.Cog`
3. Se cargará automáticamente

Ejemplo:
```python
from discord.ext import commands

class MyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def mycommand(self, ctx):
        await ctx.send("Hola!")

async def setup(bot):
    await bot.add_cog(MyCog(bot))
```

## Comparación Java vs Python

| Aspecto | Java (JDA) | Python (discord.py) |
|---------|-----------|-------------------|
| Framework | JDA 5.0.0 | discord.py 2.4.0 |
| Listeners | Clases que extienden `ListenerAdapter` | Decoradores `@commands.Cog.listener()` |
| Inicialización | `JDABuilder` | `commands.Bot` |
| Eventos | `onMessageReceived` | `on_message` |
| Logging | System.out.println | logging module |
| Estructura | Clases separadas | Cogs modulares |

## Troubleshooting

### Bot no se conecta
- Verificar token en `.env`
- Verificar permisos del bot en Discord
- Revisar logs en `logs/`

### Dependencias no se instalan
```bash
pip install --upgrade pip
pip install -r requirements.txt --force-reinstall
```

## Licencia

Mismo que el proyecto original.
