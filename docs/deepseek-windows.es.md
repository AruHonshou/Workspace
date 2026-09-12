# Credenciales de DeepSeek

El modelo configurado se valida mediante el endpoint oficial. Introduce la clave
en la interfaz; se guarda en Credential Manager, Keychain o Secret Service. Un
contenedor puede recibir `DEEPSEEK_API_KEY` o un secreto montado mediante
`DEEPSEEK_API_KEY_FILE`; los secretos inyectados son de sólo lectura. Nunca
guardes una clave real en `.env`, capturas, incidencias o repositorios.

Buscar no requiere DeepSeek. Antes de analizar o generar, revisa la vista
redactada y concede consentimiento. Borrar la credencial del vault desde
Configuración elimina el acceso local; también puedes revocarla en el proveedor.
