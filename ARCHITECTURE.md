# Arquitectura del Bot

## Flujo General

```
main.py (Entry Point)
    │
    ├─> OlimpyaBot (Bot Principal)
    │   │
    │   └─> setup_hook()
    │       │
    │       └─> load_cogs()
    │           │
    │           ├─> cogs/events.py (Eventos del Bot)
    │           │   └─> on_ready()
    │           │   └─> on_guild_join()
    │           │   └─> on_guild_remove()
    │           │
    │           └─> cogs/messages.py (Manejador de Mensajes)
    │               └─> on_message()
    │                   ├─> Registrar mensaje
    │                   └─> Buscar trigger y responder
    │
    └─> Discord Gateway Connection
        └─> Escuchar eventos
```

## Componentes

### 1. **main.py** - Punto de Entrada
- Crea instancia del bot
- Configura intents necesarios
- Inicia la conexión a Discord
- Maneja errores y cierre gracioso

### 2. **config.py** - Configuración Centralizada
- Variables de entorno
- Configuraciones de intents
- Respuestas del bot
- Fácil mantenimiento

### 3. **utils/logger.py** - Sistema de Logging
- Logs en consola con nivel INFO
- Logs en archivo con nivel DEBUG
- Timestamps automáticos
- Organización por fecha y hora

### 4. **cogs/events.py** - Eventos del Bot
Maneja eventos del ciclo de vida:
- `on_ready`: Bot conectado y listo
- `on_guild_join`: Bot agregado a servidor
- `on_guild_remove`: Bot removido de servidor

### 5. **cogs/messages.py** - Manejador de Mensajes
Lógica principal de respuesta:
1. Ignora mensajes propios
2. Registra todos los mensajes
3. Verifica triggers en `config.RESPONSES`
4. Envía respuestas automáticas

## Flujo de un Mensaje

```
Usuario envía mensaje
    │
    ├─> Discord Gateway recibe
    │
    ├─> OlimpyaBot.on_message() llamado
    │
    ├─> MessageHandler.on_message()
    │   │
    │   ├─> ¿Es del bot? → Ignorar
    │   │
    │   ├─> _log_message()
    │   │   └─> Formato: [Guild][Channel] User: message
    │   │
    │   ├─> Buscar en RESPONSES
    │   │   │
    │   │   └─> ¿Match encontrado?
    │   │       │
    │   │       ├─> Sí: Enviar respuesta + log
    │   │       │
    │   │       └─> No: Continuar
    │   │
    │   └─> process_commands() → Procesar comandos
    │
    └─> Respuesta enviada (si aplica)
```

## Patrón de Respuestas

Las respuestas automáticas se definen en `config.py`:

```python
RESPONSES = {
    "desidia": "Que pasa perro?",
    "hola": "Hola! ¿Qué tal?",
    # Agregar más aquí
}
```

- La búsqueda es **case-insensitive** (Desidia = desidia = DESIDIA)
- El mensaje debe ser **exacto** (sin espacios adicionales)
- La respuesta se envía en el **mismo canal**

## Intents Habilitados

```python
intents.default()           # Intents por defecto
intents.message_content     # Acceso al contenido del mensaje
intents.guild_messages      # Mensajes en servidores
intents.direct_messages     # Mensajes directos
```

## Cómo Extender el Bot

### Agregar Nueva Respuesta

1. Editar `config.py`
2. Agregar entrada a `RESPONSES`
3. Reiniciar bot

```python
RESPONSES = {
    "desidia": "Que pasa perro?",
    "hola": "Hola! ¿Qué tal?",  # Nueva
}
```

### Agregar Nuevo Cog

1. Crear archivo en `cogs/nueva_funcionalidad.py`
2. Crear clase con `commands.Cog`
3. Implementar listeners o comandos
4. Se cargará automáticamente

```python
# cogs/saludos.py
import discord
from discord.ext import commands

class Saludos(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command()
    async def saludo(self, ctx):
        await ctx.send(f"¡Hola {ctx.author.name}!")

async def setup(bot):
    await bot.add_cog(Saludos(bot))
```

### Agregar Comando Slash

```python
@discord.app_commands.command()
async def mi_comando(self, interaction: discord.Interaction):
    await interaction.response.send_message("Respuesta!")
```

## Manejo de Errores

Todos los cogs deben incluir manejo de errores:

```python
@commands.Cog.listener()
async def on_command_error(self, ctx, error):
    logger.error(f"Error en comando: {error}")
    await ctx.send("Hubo un error ejecutando el comando.")
```

## Seguridad

- Token guardado en `.env` (no en código)
- `.env` en `.gitignore` (no se sube a repositorio)
- Variables sensibles centralizadas en `config.py`
- Logging de acciones para auditoría

## Performance

- Cogs se cargan una sola vez
- Listeners ligeros y no bloqueantes
- Uso de `await` para operaciones asincrónicas
- Logging asincrónico cuando sea posible

## Testing

Puedes probar localmente:

```bash
# Activar entorno virtual
venv\Scripts\activate

# Instalar deps
pip install -r requirements.txt

# Configurar .env
# Ejecutar
python main.py
```

Revisar logs en `logs/bot_*.log` para debug.
