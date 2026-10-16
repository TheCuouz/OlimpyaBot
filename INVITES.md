# 🌸 Sistema de invitaciones (Fase 1 — núcleo)

Seguimiento de invitaciones para OlimpyaBot: detecta entradas/salidas, infiere qué
invitación se usó, guarda historial persistente, muestra estadísticas y ranking,
aplica reglas configurables y publica mensajes de entrada/salida.

> **Principio rector: atribución conservadora.** Discord **no** dice qué invitación
> usó un miembro; solo expone el **contador de usos** de cada invitación. Un
> incremento de usos es una **inferencia**, nunca una asociación explícita. Cuando la
> evidencia no basta, el sistema marca la entrada como **ambigua** o **sin resolver**
> en lugar de inventar un invitador.

## Piezas

| Fichero | Rol |
|---|---|
| `cogs/invites.py` | Cog: eventos de Discord, `/invites`, `/invites-admin`, mensajes de entrada/salida. |
| `utils/invites.py` | Motor puro y testeable: snapshots, diffs, atribución, elegibilidad, plantillas, `InviteTracker`. |
| `utils/invites_db.py` | Persistencia SQLite (stdlib) con migraciones versionadas. |
| `migrations/001_invite_system.sql` | Esquema documental (la sentencia viva está en `invites_db.py`). |
| `migrations/001_invite_system_down.sql` | Rollback documental (borra tablas del módulo). |
| `tests/test_invites.py` | 42 tests: lógica pura + invariantes de persistencia + integración del tracker. |
| `data/invites.db` | Base de datos real (gitignorada; `DATA_DIR` en Railway). |

## Por qué SQLite y no JSON

El módulo necesita invariantes que un JSON plano no garantiza: **una única estancia
activa por miembro**, transacciones que guardan estancia + crédito + instantánea a la
vez, índices por `guild_id` y agregados reconstruibles. `sqlite3` es de la librería
estándar → **no añade ninguna dependencia** al bot. El fichero vive en
`DATA_DIR/invites.db`, igual que `data/tickets.json`.

`TicketManager` (JSON) sigue siendo la persistencia de los **tickets**; este módulo es
independiente.

## Requisitos en Discord

- **Intents** (Developer Portal): `GUILDS`, `GUILD_MEMBERS` (privilegiado) y
  `GUILD_INVITES`. `main.py` activa `intents.members` e `intents.invites`.
- **Permisos del bot**: `Gestionar servidor` (leer invitaciones y vanity),
  `Gestionar canales` (recibir eventos de invitación crear/borrar). `Gestionar roles`
  solo hará falta en Fase 2 (recompensas por rol).
- Si falta `Gestionar servidor`, el bot **no observa** (mejor no observar que observar
  mal): `/invites-admin diagnose` lo avisa.

## Comandos

### Miembros · `/invites`
| Comando | Qué hace |
|---|---|
| `stats [usuario]` | Puntuación y desglose de un usuario (el tuyo o, para moderadores, de otro). |
| `leaderboard [pagina]` | Ranking del servidor. |
| `invited [usuario] [pagina]` | Miembros atribuidos a un usuario (visibilidad configurable). |
| `help` | Cómo funciona el sistema. |

### Administración · `/invites-admin` (solo administradores)
| Comando | Qué hace |
|---|---|
| `setup [canal]` | Activa el módulo y fija el canal de avisos (opcional). |
| `config [opciones]` | Reglas: activado, días de cuenta reciente, canal, restaurar reingreso, visibilidad, plantillas. |
| `bonus <usuario> <cantidad> <motivo>` | Ajuste firmado (+/-), auditado. |
| `inspect <usuario>` | Evidencia: estancias, origen, estado, elegibilidad. |
| `correct <estancia> <invitador> <motivo>` | Corrige a mano la atribución de una estancia (auditado). |
| `sync` | Refresca la instantánea sin inventar historial. |
| `diagnose` | Intents, permisos y estado. |
| `export` | Exporta el estado del módulo a JSON. |
| `reset <alcance>` | Reinicio acotado (con confirmación por botón). |

## Cómo se puntúa

```
puntuación = miembros válidos presentes atribuidos + ajustes manuales
```

- Un miembro = **un crédito activo** (`invite_credits`, `eligible=1`, `active=1`).
- Si **sale**, se retira ese crédito **una vez** (una salida duplicada no re-descuenta).
- **Bots** y **cuentas recientes** entran al registro pero **no puntúan**
  (`eligibility_status = excluded`).
- **Reingresos**: quien vuelve **no** genera crédito nuevo — se **restaura el crédito
  original** si era elegible. Cambiar de enlace no transfiere una recompensa ya ganada.
- Los contadores nunca se guardan como verdad única: se **calculan** desde estancias +
  créditos + ajustes.

## Atribución: qué se infiere y qué no

| Escenario | Resultado |
|---|---|
| 1 código, +1 uso, 1 entrada | `inferred` |
| 1 código, +n usos, n entradas (mismo código) | `inferred` (lote del mismo código) |
| 1 código, nº de usos ≠ nº de entradas | `ambiguous` |
| 2+ códigos incrementados a la vez | `ambiguous` (no se reparte a dedo) |
| Solo sube el vanity | `inferred` con `source_type = vanity` (sin invitador personal) |
| Vanity + código a la vez | `ambiguous` |
| Nada sube | `unresolved` |
| Primera observación / tras un reinicio | `unresolved` (línea base; no se adjudican usos históricos) |

Una invitación **borrada/agotada** se conserva como **evidencia** (`active=0`), nunca
cuenta como uso. La corrección a mano (`/invites-admin correct`) deja
`attribution_status = manual`.

## Huecos de observación

Durante una parada del bot **no** se pueden reconstruir las entradas con certeza. Al
arrancar se abre una nueva **línea base** y se registra la discontinuidad en
`invite_observation_gaps` (motivo `restart`; o `unreadable` si no se pudo leer). Las
entradas ocurridas offline no se acreditan a nadie.

## Despliegue

1. Developer Portal → activa **Server Members Intent** e **Invite Events** / `GUILD_INVITES`.
2. Invita/reinvita el bot con el scope `applications.commands` e intents actualizados.
3. `DATA_DIR` debe apuntar al volumen persistente (en Railway ya montado para tickets).
4. Arranca el bot → `/invites-admin setup` para fijar el canal de avisos (opcional).
5. `/invites-admin diagnose` para confirmar intents y permisos en verde.
6. `INVITE_ANNOUNCE_CHANNEL_ID` (env) fija el canal por defecto si no se usa `setup`.

## Rollback

- **Datos**: `/invites-admin reset all`, o a mano el SQL de
  `migrations/001_invite_system_down.sql` sobre `data/invites.db`.
- **Código**: elimina `cogs/invites.py`, `utils/invites*.py`, `tests/test_invites.py`
  y revierte las líneas de `config.py`/`main.py`/gates. El módulo **no** toca el
  esquema de tickets ni otras tablas, así que quitarlo no rompe nada más.
- Desactivación rápida sin borrar datos: `/invites-admin config activado:False`.

## Limitaciones conocidas (Fase 1)

- **No** detecta multicuentas por IP o dispositivo.
- Depende de que Discord reporte los incrementos de `uses`; con varios códigos
  incrementados a la vez la atribución queda **ambigua** a propósito.
- Las recompensas por rol (Fase 2) aún no están activas (la tabla `invite_reward_rules`
  ya existe).
- Cambiar una regla **no** recalcula el historial: cada estancia guarda el
  `rules_version` con el que se evaluó; las reglas nuevas solo afectan a entradas futuras.

## Decisiones de diseño

- **Sin dependencias nuevas**: solo `sqlite3`, `json`, stdlib.
- **El registro se persiste ANTES de anunciar**: si el mensaje de bienvenida falla, el
  historial ya está guardado (una transacción para estancia + crédito + instantánea).
- **No duplicar la bienvenida**: por defecto el canal de avisos está vacío; los
  mensajes de invitaciones solo se publican si se configura un canal.
- **Tests sin discord.py**: el motor usa *duck typing*, así que los 42 tests corren sin
  red ni token (salvo el `DISCORD_TOKEN=dummy` que exige `config.py`).
