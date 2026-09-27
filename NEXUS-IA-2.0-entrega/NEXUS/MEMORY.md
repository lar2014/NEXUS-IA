# MEMORY.md — Sistema de memoria

## Almacenamiento físico

**Dos ficheros JSON en disco, sin base de datos, sin cifrado en reposo.**

| Fichero | Gestor | Contenido |
|---|---|---|
| `memory/long_term.json` | `memory/memory_manager.py` | hechos sobre el usuario + resúmenes de sesión |
| `config/api_keys.json` | `memory/config_manager.py` | configuración: API key, nombre, voz, flags, config de plugins |

Ambos se leen/escriben con un `threading.Lock` de proceso — seguro para
concurrencia dentro de un mismo NEXUS, no diseñado para que dos procesos NEXUS
compartan el mismo fichero a la vez.

## Las 7 categorías reales dentro de `long_term.json`

```python
{
  "identity":      {},  # nombre, edad, ciudad, trabajo, idioma...
  "preferences":   {},
  "projects":      {},
  "relationships": {},
  "wishes":        {},
  "notes":         {},
  "procedural":    {},  # añadida por NEXUS — vacía, reservada, sin escritor activo salvo NexusMemory
  "sessions":      []   # lista, no dict — resúmenes de sesión (máx. 3 guardados, consumidos al leer)
}
```

Cada entrada no-sesión tiene la forma `{"value": "...", "updated": "YYYY-MM-DD"}`.
`_truncate_value()` recorta cualquier valor a 380 caracteres.

## La vista `NexusMemory` (nexus_core/memory.py)

NEXUS añade una capa de 6 vistas nombradas sobre esas 7 categorías crudas:
`short_term` (en RAM, solo turnos de esta sesión, nunca se escribe a disco
directamente — alimenta `episodic` al cerrar sesión), `episodic` (=
`sessions`), `semantic` (= `identity` + `notes` combinadas), `procedural` (=
`procedural`), `projects`, `preferences`. Los campos `relationships` y `wishes`
siguen existiendo y son totalmente accesibles vía `recall_memory` — simplemente
no tienen una vista con nombre propio en `NexusMemory`, porque nadie lo pidió.

## Qué entra en el prompt de cada sesión, y qué se busca bajo demanda

Esto es lo más importante para entender el comportamiento observable:

1. **Identidad** — siempre completa, nunca se recorta.
2. **Lo más reciente de cada categoría** — hasta `PROMPT_CORE_CHARS` (900
   caracteres), con un tope de `PROMPT_MAX_PER_CATEGORY` = 6 entradas por
   categoría, para que una categoría con 40 entradas no desplace a las demás.
3. **Un índice** de las claves que no cupieron (hasta `PROMPT_INDEX_CHARS` = 420
   caracteres) — solo los nombres, sin valores. Esto es lo que permite que el
   modelo sepa que existe un hecho aunque no esté en el prompt, y lo busque con
   la tool `recall_memory` en vez de decir "no lo sé".

`search_memory()` (usada por `recall_memory`) es una **búsqueda léxica simple**
por coincidencia de palabras — sin embeddings, sin llamada a modelo, en menos de
un milisegundo. No es RAG ni búsqueda semántica.

## Protección contra crecimiento sin control

`MEMORY_MAX_CHARS` = 200.000 caracteres es un **límite de seguridad frente a
bugs** (algo escribiendo en bucle), no un límite de producto — nada normal lo
alcanza. Si se alcanza, `_trim_to_limit()` borra las entradas más antiguas
(por `updated`) hasta volver a estar por debajo, y lo notifica al log de
actividad si hay un `_trim_notifier` registrado (lo registra `VoiceEngine.run()`
contra `ui.write_log`).

## Almacenamiento (ítem 20 del checklist)

- Sin cifrado: cualquiera con acceso al sistema de ficheros lee `long_term.json`
  y `api_keys.json` (incluida la API key de Gemini en texto plano) directamente.
  Ver SECURITY.md.
- Sin backups automáticos, sin versionado, sin límite de tamaño de fichero salvo
  el de caracteres antes descrito.
- La ruta base (`get_base_dir()`) se calcula con `sys.frozen` para funcionar
  igual como script y como ejecutable empaquetado.
