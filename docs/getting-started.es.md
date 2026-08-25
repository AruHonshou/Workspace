# Primeros pasos

[English](getting-started.md)

## Requisitos

- Windows 10/11, Python 3.12 y `uv`.
- Node.js y la versión de pnpm fijada en `package.json`.
- Una API key con saldo de DeepSeek para el análisis estructurado de agentes.
- Una API key de TheirStack para la búsqueda principal en Costa Rica.
- Tesseract sólo para OCR de PDF escaneados.

```powershell
Copy-Item .env.example .env
./scripts/bootstrap.ps1
./scripts/dev.ps1
```

Abre `http://127.0.0.1:5173`. En **Configuración**, pega cada API key en su
tarjeta y pulsa **Validar y guardar**. Las claves se validan por separado y se
guardan en el Administrador de credenciales de Windows; no se escriben en `.env`.

Después importa los CV en español e inglés, revisa y confirma sus hechos, escribe un rol y espera a
que finalice la primera tanda de hasta 25 vacantes. **Cargar 25 más** solicita y
cachea la página siguiente; puede consumir hasta 25 créditos de TheirStack. En
Resultados puedes cambiar entre 24 horas, 7 días y 30 días sin repetir la
búsqueda. **Me interesa** crea la guía PDF.

El replay sintético funciona sin API key ni red y nunca contiene datos reales.
