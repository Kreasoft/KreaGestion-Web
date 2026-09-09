# Respaldo por empresa, formato 2

La descarga de Mantenimiento contiene un JSON firmado con la clave de esta
instalación. Solo admite restauración en la misma instalación y para la empresa
identificada por ID y RUT. El límite del archivo es 100 MB. La firma acredita la
integridad; no cifra el contenido. El archivo debe custodiarse como una copia de
la base de datos, ya que ahora contiene también hashes de contraseña de las
cuentas de la empresa.

## Cobertura de tablas

`tablas` enumera las tablas físicas detectadas, sus columnas, cantidad de filas,
alcance y forma de restauración. Incluye las tablas vacías. Una tabla nueva sin
una regla de alcance provoca un error explícito: no se genera un respaldo que
la omita silenciosamente. No se exportan filas de empresas diferentes.

| Tablas | Selección | Restauración |
| --- | --- | --- |
| Modelos de negocio y perfiles | Empresa directa o relación con un padre de esa empresa | Crear faltantes y actualizar incluidos |
| `auth_user` | Usuarios cuyo perfil pertenece a la empresa, excepto superusuarios | Crear faltantes; conservar cuentas y credenciales existentes |
| `auth_group` | Grupos usados por los usuarios incluidos | Crear faltantes; conservar grupos existentes |
| Planes, permisos y tipos de contenido | Catálogos globales | Crear faltantes; conservar existentes y comprobar su identidad |
| Tablas intermedias | Relaciones de los registros incluidos | Recuperar desde el modelo de origen; conservar las de cuentas y catálogos existentes |
| Sesiones | Usuario incluido y empresa activa de la sesión coincidente | Solo consulta; no reactivar sesiones |
| Historial de acceso de Axes | Nombre de usuario actualmente asociado a la empresa; expiraciones de los intentos seleccionados | Solo consulta |
| Registro de administración | Usuario incluido y objeto perteneciente a la empresa | Solo consulta; se omiten objetos eliminados cuyo alcance no pueda comprobarse |
| Migraciones | Historial técnico global | Solo consulta; nunca marcar migraciones como aplicadas |

`registros` contiene los modelos recuperables. `relaciones` conserva también
las filas físicas de las tablas intermedias para consulta (incluidas sus PK);
al restaurar se recrean las asociaciones, no necesariamente las mismas PK
internas de las tablas intermedias. `datos_tecnicos` contiene las filas archivadas
solo para consulta.

Los usuarios globales o ajenos que aparecen como autores de operaciones se
conservan como referencias por ID; sus cuentas no se copian. Deben existir al
restaurar. No se incluyen los archivos físicos de MEDIA_ROOT: los campos de
archivo conservan sus rutas, como en un respaldo de base de datos.

## Restauración

La restauración es transaccional y no ejecuta señales de negocio. Comprueba las
relaciones, la identidad de las cuentas, la pertenencia de las PK y la cobertura
de tablas antes de escribir. Un error revierte la operación completa. Los
registros posteriores al respaldo permanecen en la base. La estructura de la
base debe corresponder a la del archivo; el respaldo no sustituye la instalación
de Django ni la ejecución de migraciones.

Los respaldos anteriores de formato 1 siguen siendo aceptados con su cobertura
original. Los enlaces históricos a otra empresa se incluyen como observaciones
en la descarga. Al restaurar se permite conservar una FK histórica únicamente
si el registro de origen sigue perteneciendo a la empresa activa y ya apunta
exactamente al mismo destino ajeno que todavía existe. No se copian registros
ajenos ni se crean vínculos cruzados nuevos. Las filas faltantes, las relaciones
modificadas y las relaciones M2M no admiten esta excepción. El resultado informa
cuántos vínculos históricos se conservaron. No se corrigen automáticamente.

Las pruebas de `utilidades.tests` verifican aislamiento, cobertura, archivos
alterados, compatibilidad con formato 1, recuperación de cuentas y permisos,
preservación de datos compartidos, registros técnicos y rollback.
