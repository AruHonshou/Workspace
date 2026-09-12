# Primeros pasos

[English](getting-started.md)

Requisitos: Python 3.12 con `uv`, Node.js 22+, la versión fijada de pnpm y
PowerShell 7. Docker es una alternativa.

```powershell
Copy-Item .env.example .env
./scripts/bootstrap.ps1
./scripts/dev.ps1
```

Abre `http://127.0.0.1:5173` y entra a AmeWork. Puedes buscar inmediatamente:
elige puesto, país, Hoy/7 días/30 días y los portales deseados. TheirStack es
opcional, pero ofrece la cobertura amplia de portales; Brete/ANE está disponible
en Costa Rica. Las búsquedas equivalentes usan la caché local y **Cargar más**
siempre es una acción manual y transparente sobre créditos.

Crea y confirma un perfil en **Mi CV** sólo cuando quieras usar herramientas de
IA. Guarda una vacante, abre su detalle y elige análisis de brechas, guía de
entrevista o CV ATS. Configura DeepSeek antes; los contactos y PDF originales
permanecen locales. En LinkedIn puedes importar el PDF de tu perfil y obtener
mejoras copiables basadas en evidencia. AmeWork nunca postula ni edita LinkedIn.
