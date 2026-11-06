# Usuarios, roles y permisos

La consola React y todos los endpoints de negocio requieren una sesión. Las cuentas se crean desde «Usuarios y permisos» por un administrador; no hay registro público ni contraseña predeterminada.

## Primera entrada

1. Inicia la API y abre la consola. En una instalación nueva aparece «Crea el primer administrador».
2. El operador del servidor lee `var/acceso/clave-inicial.txt` y usa esa clave de instalación en el formulario. La ruta cambia si se configura `NBA_AUTH_DIR`.
3. Escribe tu nombre, correo y una contraseña de al menos 15 caracteres. La primera cuenta siempre es Administrador.
4. La clave inicial deja de servir y su archivo se elimina. En las siguientes visitas se usa el correo y la contraseña de la cuenta.

`NBA_SETUP_TOKEN` permite proporcionar la clave inicial desde el entorno del servidor (mínimo 24 caracteres). Solo se utiliza al inicializar una base de usuarios nueva; no habilita un acceso posterior ni permite volver a crear el administrador.

## Permisos por rol

| Acción | Administrador | Editor | Analista de pruebas | Consulta |
|---|---|---|---|---|
| Consultar resultados, clientes, versiones y datos | Sí | Sí | Sí | Sí |
| Crear, guardar, duplicar y eliminar experimentos compartidos | Sí | Sí | Sí | No |
| Ejecutar pruebas, impacto y sensibilidad | Sí | Sí | Sí | No |
| Editar y aplicar configuración vigente | Sí | Sí | No | No |
| Exportar la parrilla | Sí | Sí | Sí | No |
| Cambiar la base activa o recuperar configuración inválida | Sí | No | No | No |
| Administrar usuarios y consultar actividad | Sí | No | No | No |
| Cambiar su propia contraseña | Sí | Sí | Sí | Sí |

«Usuarios y permisos» permite crear cuentas, cambiar nombre y rol, desactivar o reactivar cuentas y restablecer la contraseña de otra persona. Una cuenta desactivada conserva su registro y no puede entrar. El administrador no puede desactivarse ni quitarse su propio rol. La aplicación impide dejarla sin administrador activo.

Los experimentos pertenecen al espacio compartido: los tres roles que pueden gestionarlos pueden modificar la colección de pruebas. Los roles no aíslan conjuntos de clientes entre personas. Consulta puede revisar las filas y los resultados disponibles, aunque no puede ejecutar pruebas ni descargar la parrilla.

## Sesiones y actividad

La sesión dura un máximo de ocho horas. Cambiar el rol, desactivar una cuenta o restablecer su contraseña revoca todas sus sesiones. Cambiar la contraseña propia también cierra todas las sesiones de esa cuenta. El cierre de sesión invalida el identificador en el servidor.

Los permisos se comprueban en la API, independientemente de los botones disponibles. Una ruta nueva de negocio debe declarar su permiso en `api/acceso.py`; la dependencia de autorización la deniega si no lo hace. Las pruebas verifican que las rutas de negocio llevan esa dependencia.

La actividad registra el actor, la acción, el recurso y la fecha de accesos, gestión de usuarios y operaciones de configuración, datos y laboratorios. La pantalla muestra las últimas 100 entradas. Los cuerpos de peticiones, las contraseñas y los tokens no se incluyen en ese registro.

## Almacenamiento y operación

- `var/acceso/usuarios.sqlite3` conserva cuentas, sesiones, límites de intentos y actividad. La carpeta está excluida de Git y debe respaldarse por separado de `config/`. Conservarla mantiene las cuentas al reiniciar o publicar una nueva versión.
- `NBA_AUTH_DIR` elige otra carpeta para esa información. Los escenarios y las versiones de negocio permanecen en `NBA_CONFIG_DIR`.
- Las contraseñas se almacenan con scrypt, una sal aleatoria por contraseña y parámetros N=32768, r=8 y p=3. Esta es una de las combinaciones indicadas por [OWASP para almacenamiento de contraseñas](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html#scrypt).
- Los identificadores de sesión son aleatorios; la base guarda su hash. La cookie usa HttpOnly y SameSite=Strict, y cada operación de escritura exige un token CSRF vinculado a la sesión. El navegador no guarda credenciales de sesión en localStorage. Las respuestas de la API no se almacenan en cachés compartidas.
- Para servir la consola a otras personas, utiliza HTTPS y `NBA_COOKIE_SECURE=1`. La aplicación activa Secure automáticamente cuando recibe una petición HTTPS. El HTTP local permite desarrollo en `localhost`; las propiedades de la cookie y el transporte se describen en la [guía de sesiones de OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html#cookies).
- Se limitan los intentos de acceso por cuenta y dirección de cliente en ventanas de 15 minutos. Después del límite la API responde 429. Correo desconocido, contraseña incorrecta y cuenta desactivada producen el mismo mensaje de autenticación.
- CLI y Streamlit son herramientas locales del operador, con acceso directo a archivos; no pasan por esta API. No deben publicarse como una consola alternativa que permita evitar los permisos de React. Tampoco se deben servir `var/`, los YAML o la raíz del repositorio como archivos estáticos.

## Verificación

Las pruebas usan SQLite y cuentas temporales; nunca crean usuarios de demostración en la base de uso habitual. Los recorridos `npm run e2e:usuarios` y `npm run e2e:laboratorios` inician su propio servidor y realizan la instalación inicial en una carpeta desechable. Los recorridos antiguos contra una API ya iniciada (`e2e` y `e2e:aplicar`) requieren `NBA_E2E_CORREO` y `NBA_E2E_CLAVE` de una cuenta de pruebas autorizada; el recorrido de aplicación debe seguir ejecutándose con configuración temporal.

Ejecución del 2026-11-06:

```text
.venv/bin/python -m pytest -q tests/test_acceso.py
25 passed, 1 warning in 21.65s

.venv/bin/python -m pytest -q tests/test_api.py
14 passed, 1 warning in 154.05s
```

Son 39 pruebas distintas ejecutadas para esta ampliación. Se verificaron además TypeScript, la compilación de Vite y ambos recorridos completos de navegador (`e2e:usuarios` y `e2e:laboratorios`). Los recorridos comprobaron instalación inicial, creación de usuarios, permisos reales del Analista y Consulta, aplicación de una versión por el Editor, revocación al desactivar una cuenta, cambio de contraseña y conservación del funcionamiento del laboratorio. La prueba de cupos conservó 0 violaciones y un valor esperado de 10946,488863804 con la configuración temporal. Oxlint terminó sin errores nuevos; permanecen las advertencias anteriores de `store.tsx` y `graficos.tsx`, y la advertencia de tamaño del paquete de Vite.
