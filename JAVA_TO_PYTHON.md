# Migración Java → Python

Documentación de cómo se migró el código de Java (JDA) a Python (discord.py).

## Comparación de Código

### 1. Inicialización del Bot

**Java (JDA):**
```java
public class Main {
    public static void main(String[] args) throws Exception {
        JDA jda = JDABuilder.createDefault("TOKEN").build();
        jda.addEventListener(new MessageListener());
        jda.addEventListener(new ReadyEventListener());
    }
}
```

**Python (discord.py):**
```python
class OlimpyaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
    
    async def setup_hook(self):
        await self.load_cogs()

async def main():
    bot = OlimpyaBot()
    await bot.start(DISCORD_TOKEN)
```

**Diferencias:**
- JDA usa constructores síncronos; discord.py usa async/await
- Intents deben habilitarse explícitamente en Python
- Listeners de Java → Cogs en Python (más modular)
- Token en variable de entorno en Python (más seguro)

---

### 2. Event Listeners

**Java - MessageListener:**
```java
public class MessageListener extends ListenerAdapter {
    @Override
    public void onMessageReceived(MessageReceivedEvent event) {
        String messageSent = event.getMessage().getContentRaw();
        
        if (event.isFromType(ChannelType.PRIVATE)) {
            System.out.printf("[PM] %s: %s\n", 
                event.getAuthor().getName(),
                event.getMessage().getContentDisplay());
        } else {
            System.out.printf("[%s][%s] %s: %s\n",
                event.getGuild().getName(),
                event.getChannel().getName(),
                event.getMember().getEffectiveName(),
                event.getMessage().getContentDisplay());
        }
        
        if(messageSent.equalsIgnoreCase("Desidia")){
            event.getChannel().sendMessage("Que pasa perro?").queue();
        }
    }
}
```

**Python - MessageHandler Cog:**
```python
class MessageHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return
        
        self._log_message(message)
        
        content = message.content.lower().strip()
        for trigger, response in RESPONSES.items():
            if content == trigger:
                await message.channel.send(response)
                logger.info(f"Respuesta: {response}")
                break
    
    def _log_message(self, message):
        if isinstance(message.channel, discord.DMChannel):
            logger.info(f"[PM] {message.author.name}: {message.content}")
        else:
            logger.info(
                f"[{message.guild.name}][{message.channel.name}] "
                f"{message.author.display_name}: {message.content}"
            )
```

**Diferencias:**
- JDA: `ListenerAdapter` con métodos `on*Event`; Python: Decoradores `@listener()`
- JDA: `.queue()` para operaciones async; Python: `await` nativo
- JDA: `System.out.printf()` para logging; Python: módulo `logging`
- Java: Case insensitive con `.equalsIgnoreCase()`; Python: `.lower().strip()`
- Python más escalable: respuestas en diccionario `RESPONSES`

---

### 3. Event Ready

**Java - ReadyEventListener:**
```java
public class ReadyEventListener implements EventListener {
    public void onEvent(GenericEvent event) {
        if (event instanceof ReadyEvent)
            System.out.println("El bot está listo y online, sigue toqueteando, a ver que encuentras");
    }
}
```

**Python - Events Cog:**
```python
class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f"El bot está listo y online como {self.bot.user}")
        logger.info(f"Conectado a {len(self.bot.guilds)} servidor(es)")
        await self.bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="a los usuarios"
            )
        )
```

**Mejoras:**
- Python muestra más información (nombre del bot, número de servidores)
- Establece "status" del bot automáticamente
- Logging estructurado en lugar de print

---

## Mejoras Implementadas

### 1. **Arquitectura Modular**
- Java: Clases separadas que heredan de listeners
- Python: Cogs que se cargan dinámicamente → Más escalable y mantenible

### 2. **Configuración Centralizada**
- Java: Token hardcodeado en código
- Python: Variables de entorno en `.env` → Más seguro

### 3. **Logging Profesional**
- Java: `System.out.println()`
- Python: Logging dual (consola + archivo con timestamps)

### 4. **Manejo de Errores**
- Java: Pocas excepciones capturadas
- Python: Try/catch con logging de errores

### 5. **Extensibilidad**
- Java: Requiere agregar listener manualmente
- Python: Cogs se cargan automáticamente del directorio `cogs/`

### 6. **Respuestas Escalables**
- Java: Un if por respuesta
- Python: Diccionario en `config.py` → Agregar respuestas sin tocar código

---

## Mapeo de Conceptos

| Concepto Java | Concepto Python | Ubicación |
|---------------|-----------------|-----------|
| `JDABuilder` | `commands.Bot()` | `main.py` |
| `ListenerAdapter` | `commands.Cog` | `cogs/` |
| `@Override onMessageReceived()` | `@Cog.listener() on_message()` | `cogs/messages.py` |
| `@Override onEvent()` | `@Cog.listener() on_ready()` | `cogs/events.py` |
| `.queue()` | `await` | Todo (nativo) |
| `.equalsIgnoreCase()` | `.lower()` | `cogs/messages.py` |
| `System.out.println()` | `logging.info()` | `utils/logger.py` |
| Token hardcodeado | Variables de entorno | `.env` |
| Instancias manuales | Carga dinámica | `load_cogs()` |

---

## Ventajas de la Versión Python

✅ **Más Legible**: Python es más simple y directo
✅ **Más Seguro**: Token en `.env`, no hardcodeado
✅ **Más Mantenible**: Cogs modulares
✅ **Mejor Logging**: Logs en archivo + consola
✅ **Fácil de Extender**: Agregar respuestas en diccionario
✅ **Menos Dependencias**: Una librería principal (discord.py vs JDA)
✅ **Configuración Clara**: `config.py` centralizado
✅ **Async Nativo**: `async/await` directo, no `.queue()`

---

## Cómo Usar la Versión Python

Ver [QUICKSTART.md](QUICKSTART.md) para instrucciones de instalación.

## Diferencias en Comportamiento

| Aspecto | Java | Python |
|---------|------|--------|
| Intents | Implícitos | Explícitos |
| Async | `.queue()` | `await` |
| Configuración | Hardcodeado | Variables de entorno |
| Estructura | Clases separadas | Cogs modulares |
| Logging | stdout | archivo + consola |
| Respuestas | If/else | Diccionario |
| Carga de listeners | Manual | Automática |

