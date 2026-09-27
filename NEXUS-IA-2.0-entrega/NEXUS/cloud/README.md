# cloud/ — Nexus Cloud (parcialmente desplegado)

Esta carpeta es intencionadamente distinta del resto del proyecto: todo lo que
hay fuera de `cloud/` es el **Agent** (la app de escritorio que ya tenías,
Windows hoy). Lo que hay aquí dentro es **Nexus Cloud**, el "cerebro" de la
visión multiusuario.

## Estado real (no idealizado)

- **Supabase: desplegado y verificado de verdad.** Proyecto `nexus-cloud`
  (`ipdgezppzuwvrgzfwwpu`, `eu-west-1`, 0 €/mes), esquema aplicado
  (`schema.sql` + migraciones de storage y Vault), RLS limpio según el
  asesor de seguridad de Supabase, bucket `user-files` listo.
- **Vercel: proyecto creado, backend con un bug corregido pendiente de
  publicar.** El primer despliegue (con el bug de `api/health.ts` descrito
  abajo) se hizo con éxito vía API. Los intentos posteriores de volver a
  desplegar el fix chocaron con un **403: "You don't have permission to
  create a Production Deployment for this project"** — probado con
  `target: production` y `target: preview`, mismo resultado. Es una
  restricción de permisos de la integración de Vercel de esta sesión sobre
  un proyecto ya existente, no un problema de código ni de datos.

## El bug ya corregido en este código, pendiente de subir

`api/health.ts` hacía `throw error` con el error de Supabase (un objeto
plano, no una instancia de `Error`) y luego `String(err)` — eso produce
literalmente `"[object Object]"` en vez del mensaje real. Ya está corregido
en el fichero de esta carpeta (lee `error.message`/`.details`/`.hint`/`.code`
directamente). Falta ponerlo en producción por una de estas dos vías:

**Opción A — Vercel CLI (más rápido, sin tocar Git):**
```bash
cd cloud/nexus-cloud
npm install -g vercel   # si no la tienes
vercel login            # con tu propia cuenta
vercel link              # elige el proyecto "nexus-cloud" ya existente
vercel --prod
```

**Opción B — conectar un repositorio Git (recomendado a medio plazo):**
sube esta carpeta a un repositorio de GitHub tuyo y conéctalo desde
Vercel Dashboard → nexus-cloud → Settings → Git. A partir de ahí, cada
`git push` despliega solo — es también el camino natural para cuando
quieras que otro colaborador (o yo, con permisos de repo) toque este código.

- No hay todavía ningún backend que autentique un frontend real ni una
  pantalla de login — el siguiente paso natural es decidir dónde vive esa
  pantalla (¿Nexus Agent la abre en el navegador? ¿un frontend propio?).
