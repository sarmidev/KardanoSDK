# Kardano SDK - Phase 1 Plan

## Objetivo

Phase 1 convierte la base de Phase 0 en un primer flujo MVP verificable en una app
Android. La prioridad no es construir todo de golpe, sino avanzar por bloques pequenos
con checkpoints donde se pueda abrir la app y comprobar que la funcionalidad integrada
realmente responde.

El objetivo final de Phase 1 es un flujo preprod/testnet:

1. Crear o restaurar una wallet de prueba.
2. Derivar una direccion.
3. Consultar UTxOs.
4. Construir una transaccion ADA simple.
5. Firmarla localmente.
6. Enviarla a preprod.
7. Ver el resultado desde la app Android.

No se usan mainnet ni fondos reales en esta fase.

## Principio de trabajo

Cada bloque debe tener una frontera clara:

- Que se implementa.
- Que no se implementa.
- Que se puede probar en Android.
- Que tests/docs quedan actualizados.
- Que decisiones quedan abiertas para el siguiente bloque.

Los checkpoints Android son parte del plan, no un extra al final. Si una funcionalidad no
puede verse todavia en Android, debe quedar claro por que y que desbloquea.

## Decisiones del Bloque 1.1

Bloque 1.1 (planificacion/documentacion, sin codigo) deja registradas las siguientes
decisiones antes de tocar wallet, crypto, provider, tx o UI de Android. Ver tambien
`docs/DECISIONS/0005-phase-1-architecture-and-scope.md` (ADR-0005).

Decisiones tomadas ahora:

- **Flujo MVP (preprod, verificado en Android):** crear/restaurar wallet de prueba ->
  derivar una direccion -> consultar UTxOs -> construir una tx ADA-only minima -> firmar
  localmente -> enviar a preprod -> mostrar el resultado. Corresponde a los bloques 1.6-1.11.
- **Native assets: fuera del primer MVP.** Solo ADA (pago + change). Se reconsideran despues
  del cierre de Phase 1 o en Phase 2.
- **Android es el objetivo primario de Phase 1.** iOS/Desktop se mantienen solo en modo
  compilacion durante Phase 1 (salvo que se decida explicitamente lo contrario); sus
  checkpoints funcionales quedan para el cierre de Phase 1 (1.12) o Phase 2. Esto reduce el
  alcance frente a los criterios de aceptacion de Phase 1 en `docs/ROADMAP.md`, que hoy piden
  demos de iOS y JVM/Desktop; ese documento se actualiza junto con este bloque.
- **Estrategia de modulos/paquetes: solo criterios de decision, no se crea ningun modulo en
  este bloque.**
  - Paquetes primero, unicamente donde el trabajo sea libre de dependencias y los limites de
    propiedad ("ownership") todavia esten en exploracion.
  - Cualquier implementacion que introduzca dependencias de crypto, provider o red es un
    disparador probable para crear un modulo Gradle real.
  - `:core` se mantiene libre de dependencias y estructural.
  - `:shared` se mantiene como host de muestra/UI y no debe convertirse en el hogar
    definitivo de la logica de crypto/wallet/tx/provider del SDK.
  - La creacion real de modulos queda diferida al primer bloque de implementacion que
    necesite separacion de dependencias/ownership (segun ADR-0002/ADR-0003).
  - No se afirma que los paquetes de crypto/provider vayan a vivir en `:core` ni en
    `:shared`; su hogar se decide cuando corra el bloque que dispare esa separacion.
- **Provider: mock/stub primero, Blockfrost como primer provider real de preprod.** Se
  define una interfaz de provider en el Bloque 1.3 junto con una implementacion mock, para
  que el trabajo de wallet/tx pueda avanzar sin depender de red real; despues se conecta
  Blockfrost en preprod. Koios, Maestro, Ogmios y Kupo quedan diferidos (Phase 2). La API
  publica del provider se mantiene minima para evitar bloquear el diseño futuro.
- **Alcance de datos del provider para el MVP:** UTxOs por direccion, parametros de
  protocolo, endpoint de submit. Cualquier otro dato (historial de tx, metadata) queda
  diferido.
- **Ruta de decision de crypto:** la evaluacion de librerias/bindings de ADR-0004 sigue
  siendo el bloqueante real para wallet; se mantiene como Bloque 1.4 (evaluacion) y 1.5
  (primitivas), pero los bloques read-only 1.2 y 1.3 pueden avanzar en paralelo porque no
  requieren crypto. Algoritmos a resolver primero: Ed25519-BIP32, derivacion BIP-32/CIP-1852,
  BIP-39/CIP-3, PBKDF2-HMAC-SHA-512, HMAC-SHA-512, Blake2b-224/256. La matriz de candidatos de
  ADR-0004 se actualiza en 1.4/1.5, no en este bloque; aqui no se selecciona ninguna libreria.
- **Definicion de "transaccion ADA minima":** una o mas entradas seleccionadas de los UTxOs
  de la wallet, una salida de pago a una direccion `addr_test` destino, una salida de change,
  una fee calculada, y un intervalo de validez solo si resulta necesario. Sin native assets,
  metadata, certificados ni scripts.
- **Prerrequisitos de CBOR/serializacion antes de construir transacciones:** queda pendiente
  decidir si la serializacion de tx de Cardano necesita el orden de mapas RFC 7049
  "length-first" en vez de la regla bytewise de RFC 8949 §4.2.1 usada en Phase 0 (item
  abierto de ADR-0001); y queda pendiente una politica de encoding/roundtrip de direcciones
  (`Address.parse` hoy es solo decode; generar direcciones en 1.7 necesita `toBech32` o
  equivalente, lo cual requiere su propio ADR). Ambos se resuelven en sus propios bloques
  (CBOR en 1.9, direcciones antes/en 1.7), no aqui.
- **Alcance de fee/change:** un calculo de fee directo a partir de los parametros de
  protocolo mas una estrategia de change simple en el Bloque 1.9; sin coin selection
  avanzada.

Decisiones diferidas explicitamente (no se resuelven en 1.1):

- Libreria/binding concreto de crypto por algoritmo -> Bloque 1.4/1.5 (actualiza la matriz de
  ADR-0004).
- Limites finales de modulos Gradle y su momento exacto -> cuando aparezca presion de
  dependencias (probablemente en 1.3/1.4).
- ADR de encoding/roundtrip de direcciones (necesario para la generacion en 1.7) -> ADR propio
  antes de/en 1.7.
- Orden de mapas CBOR para serializacion de tx -> trabajo de serializacion de tx (1.9).
- Modelo de persistencia de wallet -> no se improvisa junto con signing; decision separada.
- Native assets, Byron/Base58, flujos funcionales de iOS/Desktop, providers adicionales ->
  stretch de Phase 1 o Phase 2.

Limites de alcance / riesgo (se repiten en ADR-0005):

No mainnet; no claves privadas, mnemonics ni fondos reales en ningun lugar; no crypto
escrita a mano; no firma de transacciones antes de aprobar el alcance de crypto + provider +
tx; no se debilitan validadores; no se agregan dependencias nuevas en este bloque
(las dependencias solo se justifican en un bloque de implementacion posterior); `:core` se
mantiene libre de UI y de dependencias; `:shared` se mantiene como host de muestra/UI y no es
el hogar definitivo de la logica de crypto/wallet/tx/provider del SDK.

## Bloques propuestos

### 1.1 Phase 1 Scope And Architecture Plan

Status: complete.

Bloque de planificacion. No implementa crypto, wallet, provider ni transacciones.

Objetivo:

- Definir el alcance exacto del MVP de Phase 1.
- Decidir que modulos se crean ahora y cuales se aplazan.
- Definir los boundaries iniciales entre `:core`, posible `:crypto`, `:wallet`, `:tx`,
  `:provider` y apps de ejemplo.
- Elegir el primer provider objetivo para preprod, o dejar una decision concreta pendiente.
- Definir las pantallas minimas de Android para validar cada bloque.
- Definir que datos son solo de prueba.

Outcome:

- Vease la seccion "Decisiones del Bloque 1.1" arriba y
  `docs/DECISIONS/0005-phase-1-architecture-and-scope.md` (ADR-0005, Accepted) para el
  detalle completo. Resumen: flujo MVP ADA-only definido (1.6-1.11); native assets fuera del
  primer MVP; Android como objetivo primario, iOS/Desktop solo compilacion en Phase 1; la
  estrategia de modulos/paquetes queda como criterios de decision (sin crear modulos ahora,
  sin asumir que crypto/provider viven en `:core` o `:shared`); provider mock/stub primero
  con Blockfrost como primer candidato real de preprod; ruta de decision de crypto delegada a
  ADR-0004 en los Bloques 1.4/1.5; y los prerrequisitos de direcciones (ADR de
  encoding/roundtrip) y de CBOR (orden de mapas para tx) quedan explicitamente diferidos a
  sus propios bloques. Sin cambios de Kotlin, Gradle o dependencias en este bloque.

Checkpoint Android:

- Baseline verificado por compilacion: `./gradlew :androidApp:assembleDebug :core:jvmTest`
  compila la app Android de muestra y `:core` sin cambios de codigo. Esto confirma que la APK
  se ensambla, no que se abrio manualmente; una verificacion manual de apertura es opcional y,
  si se realiza, la registra el owner por separado.

### 1.2 Android SDK Playground

Status: complete.

Objetivo:

- Tener un sitio visible donde probar el SDK durante toda Phase 1.
- Parsear direcciones `addr_test` / `stake_test`.
- Mostrar `network`, `AddressType`, credentials y pointer cuando aplique.
- Probar errores tipados de direccion de forma comprensible.
- Opcionalmente exponer checks simples de Hex, Bech32 y CBOR.

Outcome:

- Nuevo paquete `org.sarmidev.kardano.playground` en `:shared` `commonMain`:
  - `PlaygroundPresenter`: objeto puro sin imports de Compose que mapea
    `KardanoResult<Address, AddressError>` a filas etiquetadas (network, type, hrp,
    credential kind, hash corto de 6 bytes con caption "structural only") o a un mensaje
    de error legible por variante. Incluye `internal fun presentAddressError(error)` para
    que los tests puedan construir variantes de `AddressError` directamente sin depender
    de inputs concretos. Tambien expone `presentHexDecode` y `presentCbor` (hex -> CBOR
    decode + re-encode round-trip).
  - `PlaygroundScreen`: `@Composable internal` con estado local (`remember mutableStateOf`),
    sin ViewModel ni framework de navegacion. Secciones: parseador de direcciones con
    visualizacion de errores tipados, decodificador Hex, decodificador CBOR.
  - `App.kt` reemplazado para renderizar `PlaygroundScreen()` dentro de `MaterialTheme`.
    `:core` no se modifica; `:androidApp` no se modifica; sin nuevas dependencias ni modulos
    Gradle; `:shared` no replica la suite de vectores de protocolo de `:core`; solo usa
    un numero minimo de vectores CIP-19 citados para comprobar el wiring del presenter.
- Tests en `shared/src/commonTest`: `PlaygroundPresenterTest` cubre 11 variantes de
  `AddressError` construidas directamente, 2 happy paths CIP-19 citados (`type-06`
  enterprise testnet y `type-14` reward testnet), 1 input invalido simple y 1 test de
  estado Empty. No se replica la suite de vectores de protocolo de `:core`.
- Verificacion: `./gradlew :core:jvmTest`, `:shared:jvmTest`, `:shared:testAndroidHostTest`,
  `:shared:compileKotlinIosSimulatorArm64`, `:androidApp:assembleDebug` — todos BUILD
  SUCCESSFUL.
- UI tests / Compose UI / Espresso diferidos; el checkpoint manual es la verificacion del
  bloque.

Checkpoint Android (verificado por el owner el 2026-07-05):

1. `./gradlew :androidApp:assembleDebug` — APK instalado y app abierta.
2. La pantalla del Playground se renderiza (titulo, campo de entrada, area de resultado).
3. Pegado `addr_test1vz2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzerspjrlsz` → visto
   `Network: TESTNET`, `Type: ENTERPRISE`, `HRP: addr_test`, credential kind, y hash
   prefijo corto con caption "structural only". ✓
4. Pegado `stake_test1uqehkck0lajq8gr28t9uxnuvgcqrc6070x3k9r8048z8y5gssrtvn` → visto
   `Type: REWARD`, `Network: TESTNET`, stake credential kind. ✓
5. Input invalido → mensaje de `AddressError` legible, sin crash. ✓
6. Hex decoder con `010203` → resultado correcto. ✓
   CBOR decoder con `43010203` → `CborByteString` decodificado y round-trip ok. ✓

Solo se usan vectores publicos de CIP-19 — sin fondos reales ni datos privados.

### 1.3 Provider Read-Only Boundary

Definir y probar la capa de consulta de red antes de crear wallets. El bloque se divide en
1.3a (interfaz + modelos + mock, sin red ni secrets) y 1.3b (Blockfrost preprod real,
diferido). Ver `docs/DECISIONS/0006-provider-boundary-and-strategy.md` (ADR-0006, Accepted).

Objetivo:

- Definir una interfaz de provider para consultas read-only, neutral respecto al backend.
- Consultar UTxOs de una direccion.
- Consultar parametros de protocolo necesarios para el fee/build futuro.
- Modelar errores con tipos claros y neutrales (sin filtrar formas de Blockfrost).
- Empezar con una implementacion mock/stub; el provider real de Blockfrost queda para 1.3b.

#### 1.3a Interfaz + modelos + mock (este bloque)

Status: complete.

Outcome:

- Nuevo modulo Gradle KMP `:provider` (Android library + JVM + iosArm64 + iosSimulatorArm64,
  `explicitApi()`), que depende solo de `:core`. Justificado por *ownership* (el provider no
  puede vivir en `:core`, que es dependency-free, ni quedarse en `:shared`, host de
  muestra/UI). `:provider` `commonMain` no agrega dependencias; solo `commonTest` usa
  `kotlinx-coroutines-test` (pinneado en el catalogo).
- Paquete `org.sarmidev.kardano.provider`:
  - `ChainQueryProvider`: interfaz read-only con `val network: Network` y funciones `suspend`
    `getUtxos(Address)`, `getProtocolParameters()`, `getTip()`, todas devolviendo
    `KardanoResult` (nunca lanzan). Submit **no** esta aqui: ADR-0006 refina ADR-0005 §5
    separando la consulta read-only de un futuro `TxSubmitProvider` (Bloque 1.11).
  - Modelos ADA-only y neutrales: `Utxo` (`UtxoRef` de `:core` + `Value`), `Value` (envuelve
    `Lovelace`, deja espacio para multiasset futuro sin prometer compatibilidad), `ProtocolParameters`
    (campos de fee/build como `Long`), `ChainTip`. `ProviderError` sellado (`Transport`,
    `RemoteStatus(code)` transport-agnostico —no `HttpStatus`—, `NotFound`, `Deserialization`,
    `RateLimited`, `NetworkMismatch`, `Unknown`).
  - `InMemoryChainQueryProvider`: doble de muestra/test con datos **fake / solo de prueba**
    (sin red, sin fondos, sin secrets, no son fixtures de cadena). Reconoce dos direcciones
    seed documentadas (vectores CIP-19 testnet publicos): una con UTxOs
    (`SEED_ADDRESS_WITH_UTXOS`) y otra vacia (`SEED_ADDRESS_EMPTY`). Devuelve `NetworkMismatch`
    si la red de la direccion no coincide con la del provider (`Network.TESTNET` por defecto;
    `TESTNET` no identifica preprod frente a preview por si solo).
- Playground (`:shared` depende de `:provider`): nueva seccion "Provider (mock)" con campo de
  direccion, botones para rellenar las direcciones seed, "Load UTxOs (mock)" y "Load protocol
  params (mock)"; muestra filas de UTxO, el estado "sin UTxOs", parametros y errores tipados,
  todo etiquetado como fake/test-only. Las llamadas `suspend` se disparan con `LaunchedEffect`
  (sin dependencias de coroutines nuevas en `:shared`). El mapeo puro se extrajo a funciones
  `internal` no-suspend (`mapUtxosResult`, `mapParamsResult`, `presentProviderError`) para
  poder testear sin coroutines.
- Tests: `:provider` `commonTest` (con `runTest`) cubre UTxOs seed, estado vacio,
  `NetworkMismatch`, parametros y tip. `:shared` `commonTest` cubre el mapeo del presenter
  (success/empty/failure/params y las siete variantes de `ProviderError`).
- Verificacion: `./gradlew :core:jvmTest :provider:jvmTest :provider:testAndroidHostTest
  :provider:compileKotlinIosSimulatorArm64 :shared:jvmTest :shared:testAndroidHostTest
  :shared:compileKotlinIosSimulatorArm64 :androidApp:assembleDebug` — todos BUILD SUCCESSFUL.

#### 1.3b-pre Address source-string microchange (completado)

- Cambio aditivo minimo en `:core`: `Address` expone `public val bech32`, el string validado
  exacto pasado a `Address.parse`, hilado por los caminos fixed-size y pointer y excluido de
  `equals`/`hashCode`/`toString`. Es la representacion fuente validada, no un `toBech32`
  (el encoding/roundtrip sigue diferido a 1.7). Desbloquea los endpoints de Blockfrost
  indexados por direccion sin anadir un encoder. Se landeo aparte por tocar API publica.

#### 1.3b Blockfrost preprod real (completado)

- Modulo `:provider-blockfrost` (depende de `:provider` + `:core`) con `BlockfrostChainQueryProvider`,
  cliente HTTP Ktor (engines OkHttp/CIO/Darwin) y kotlinx-serialization, todo aislado en el
  modulo (`:core` y `:provider` siguen sin HTTP). DTOs `internal @Serializable`; mapeo a los
  modelos neutrales (UTxOs con paginacion y suma ADA-only, parametros, tip, `404`-como-vacio en
  `getUtxos`, mapeo de errores a `Transport`/`RateLimited`/`RemoteStatus`/`NotFound`/`Deserialization`).
  `BlockfrostNetwork { PREPROD, PREVIEW, MAINNET }` mapea a `Network`. API key en runtime/env/
  `local.properties` (sin secrets en el repo). Tests con `MockEngine` + fixtures sanitizadas;
  test de integracion real opt-in condicionado a `BLOCKFROST_PROJECT_ID` (omitido por defecto).
  Consume el `Address.bech32` ya landeado (1.3b-pre); no lo introduce. Submit sigue en 1.11
  (ADR-0006). Ver ADR-0007.

Checkpoint Android (1.3a, mock):

- Abrir la app, ir a "Provider"; con la direccion seed con UTxOs -> lista de UTxOs
  (`txHash#index -> lovelace`); con la direccion seed vacia -> estado "sin UTxOs"; direccion
  invalida -> error tipado sin crash; "Load protocol params" -> filas de parametros.
  Todo con la etiqueta fake/test-only, sin red ni secrets.

Checkpoint Android (1.3b, live) — a ejecutar por el owner con su propia key:

- Activar "Use live Blockfrost (preprod)", pegar un `project_id` de preprod y un `addr_test1...`
  real -> UTxOs/parametros reales; key invalida -> `RemoteStatus`/`Transport` tipado sin crash;
  direccion sin uso -> estado vacio. La key no se persiste.

### 1.4 Crypto Evaluation And Module Decision

Status: complete. Bloque de decision/evaluacion (solo docs), basado en ADR-0004. Ver
`docs/DECISIONS/0008-crypto-dependency-evaluation-and-module-decision.md` (ADR-0008).

Objetivo:

- Evaluar librerias/bindings concretos para los algoritmos que Phase 1 necesita.
- Decidir si se crea `:crypto` ahora o si se empieza con un paquete aislado.
- Registrar decisiones en ADR-0004 o en un ADR nuevo si hace falta.
- No implementar wallet completa en este bloque.

Outcome:

- Se anadio ADR-0008 (`Accepted` solo para las decisiones de modulo/seam/proceso; sin afirmar
  idoneidad final de ninguna dependencia mientras la compatibilidad no se pruebe). Sin cambios
  de Kotlin, Gradle, dependencias ni modulos en este bloque; solo docs.
- **Decidido ahora:** (1) `:crypto` se difiere al Bloque 1.5 (el bloque que anade la primera
  dependencia de crypto), consistente con ADR-0002/0005; (2) el seam es una interfaz comun /
  adapter en `commonMain` (`Hashing`, luego `KeyDerivation` / `Signing`) que devuelve
  `KardanoResult` y no lanza a traves de Swift/ObjC, con `expect`/`actual` solo como fallback;
  (3) el primer limite algoritmico en 1.5 es Blake2b-224/256 detras de `Hashing`, con vectores
  oficiales citados (RFC 7693 / contexto Cardano) — sin inventar vectores.
- **Provisional:** la seleccion de dependencia es provisional. Hyperledger Identus Apollo +
  `bip32-ed25519` es el lider provisional (unico candidato evaluado que cubre todos los targets
  y el set completo incluyendo Ed25519-BIP32), pero su compatibilidad con Kotlin 2.4.0 esta sin
  probar. Matriz de candidatos con hechos citados por fuente y desconocidos marcados
  `Unverified` / `To verify in 1.5a`; estado de revision de terceros con campos neutrales
  (`External review`, `Public review notes`), sin claim de idoneidad.
- **Rechazado como dependencia enviada:** bloxbean cardano-client-lib (JVM/Java, sin iOS/KMP);
  se conserva solo como oraculo de vectores en JVM.

Checkpoint Android:

- Mantener la app compilando. Este bloque desbloquea los siguientes, aunque no tenga una
  pantalla funcional nueva.

### 1.5 Crypto Primitives Needed For Wallet

Implementar solo las primitivas necesarias para el MVP de wallet, siguiendo ADR-0004 y las
decisiones de ADR-0008. Se divide para no comprometer una dependencia sin probarla primero.

#### 1.5a Compatibility spike (antes de cualquier dependencia comprometida)

- En una rama desechable, anadir el candidato provisional (Apollo + `bip32-ed25519`, y sus
  companions transitivos, p. ej. `secp256k1-kmp`) a un modulo scratch.
- Confirmar que resuelve y compila en Android + JVM + iosSimulatorArm64 bajo la version de
  Kotlin del repo (hoy `2.4.0`).
- Si falla, descartar la rama y repetir 1.5a con el siguiente fallback (composicion
  multi-libreria: cryptography-kotlin + fuente Blake2b + libreria Ed25519-BIP32; luego el
  platform seam A+B de ADR-0004).
- Registrar el resultado (candidato, targets, versiones) en ADR-0008 o en una nota de
  seguimiento corta. No se compromete ninguna dependencia al build antes de que 1.5a pase.

Resultado (2026-07-11): **PASS.** En una rama desechable (`spike/1.5a-apollo-kotlin24`, ya
descartada) con un modulo scratch `:crypto-spike` que dependia solo de los dos artefactos
candidatos, el candidato **resolvio y compilo** en los tres targets bajo Kotlin 2.4.0 / AGP 9.0.1:
`:crypto-spike:compileKotlinJvm`, `:crypto-spike:compileKotlinIosSimulatorArm64` y
`:crypto-spike:testAndroidHostTest` (`compileAndroidMain`). Versiones resueltas:
`org.hyperledger.identus:apollo:1.8.8` y `dev.allain:bip32-ed25519:2.3.0`. Correccion: no hizo
falta `org.hyperledger.identus:secp256k1-kmp:1.8.8`; Apollo arrastra
`fr.acinq.secp256k1:secp256k1-kmp:0.16.0` transitivamente. Esto prueba resolucion +
compilacion/typecheck (incluido el klib de iOS sim), no correccion criptografica ni ejecucion en
runtime. La adopcion/cableado concretos se deciden en 1.5b. Detalle en ADR-0008 §6.

#### 1.5b-pre Gate de vectores (docs-only, antes de crear `:crypto`)

Antes de crear `:crypto` o escribir el API de hashing, un gate bloqueante busca vectores
oficiales, citados y exactos (bytes de entrada + digest exacto + URL/commit) para ambos
tamanos. Resultado (2026-07-11): ambos tamanos **PASS**.

- Blake2b-224: **PASS.** Par oficial de CIP-19 (CC-BY-4.0): clave de verificacion
  `addr_vk1w0l2sr2zgfm26ztc6nl9xy8ghsk5sh6ldwemlpmp9xylzy4dtf7st80zhd` (decodificable por
  bech32 a 32 bytes) + los 28 bytes de payment credential extraibles de la direccion CIP-19
  completa `addr1qx2fxv2umyhttkxyxp8x0dlpdt3k6cwng5pxj3jhsydzer3n0d3vllmyqwsx5wktcd8cc3sq835lu7drv2xwl2wywfgse35a3x`
  via `Address.parse` de `:core`.
- Blake2b-256: **PASS.** Goldens de conformance de Plutus para el builtin sin clave
  `blake2b_256` (Apache-2.0), repo `IntersectMBO/plutus`, commit
  `5e18824e2e0e30656c81d182e0ca512b75e7e57c`, prefijo de ruta
  `plutus-conformance/test-cases/uplc/evaluation/builtin/semantics/blake2b_256/`.
  Vector 1 (`blake2b_256-empty`): input `#` (0 bytes) → `0e5751c026e543b2e8ab2eb06099daa1d1e5df47778f7787faab45cdf12fe3a8`.
  Vector 2 (`blake2b_256-length-200`): input `2e7ea84da4bc4d7cfb463e3f2c8647057afff3fbececa1d200`
  (25 bytes) → `91c60f99b33303c02b39ed93b713e3915a180c3747f3b31e05727618ee401624`.
  Validacion: cada fixture es `equalsByteString (blake2b_256 (con bytestring #INPUT)) (con bytestring #EXPECTED)`
  con `.uplc.expected` = `(con bool True)`; el builtin se aplica solo a los bytes crudos del
  literal UPLC (sin envoltura CBOR/UPLC), `#` = vacio y `#2e7e…1d200` = exactamente 25 bytes. El
  digest de entrada vacia `0e5751c0…`, antes rechazado por aparecer solo en un repo Rust de
  terceros, queda confirmado literalmente en esta fuente oficial de Intersect.

Consecuencia: con ambos tamanos fijados, el gate `1.5b-pre` pasa y `1.5b` queda desbloqueado.
`1.5b-pre` no crea modulo, dependencia ni cambios de Kotlin/Gradle; solo docs. Detalle en
ADR-0008 §7.

#### 1.5b Wire + test (desbloqueado; vectores ya fijados en 1.5b-pre)

Status: complete.

Objetivo:

- Crear `:crypto` y anadir la dependencia elegida (pineada, sin versiones dinamicas).
- Cablear el primer limite algoritmico: Blake2b-224/256 detras de la interfaz `Hashing`.
- Implementar wrappers/bindings de los algoritmos elegidos.
- Cubrirlos con vectores oficiales citados (Blake2b-224 CIP-19, Blake2b-256 IntersectMBO/plutus);
  sin inventar vectores.
- Mantener errores tipados (`KardanoResult`, sin lanzar a traves de Swift/ObjC).
- Evitar exponer bytes mutables internos.
- No firmar transacciones todavia si se puede separar.

Outcome:

- Nuevo modulo KMP `:crypto` (Android library + JVM + iosArm64 + iosSimulatorArm64,
  `explicitApi()`) que depende solo de `:core`. `:core` no depende de `:crypto`.
- Paquete `org.sarmidev.kardano.crypto`: `Hashing` (`blake2b224`/`blake2b256`, ambos devuelven
  `KardanoResult<HashDigest, CryptoError>`, nunca lanzan) con `Hashing.default()`; `HashDigest`
  (clase regular, constructor privado, factory interna que valida tamano, copias defensivas,
  igualdad por contenido, `toString` estructural, constantes `SIZE_224`/`SIZE_256`); `CryptoError`
  sellado y neutral respecto al backend (`HashingFailed`, `InvalidDigestLength`). Adapter interno
  `Blake2bHashing`; ningun tipo del backend aparece en la API publica.
- **Correccion de dependencia:** al cablear se comprobo que **Apollo 1.8.8 no incluye Blake2b**
  (verificado en el `apollo-jvm-1.8.8.jar` publicado —su paquete `hashing` solo trae
  `PBKDF2SHA512`— y en los tags de fuente `v1.7.2`–`v1.8.7`). Como ADR-0004 prohibe crypto escrita
  a mano, el backend de este bloque solo-hashing es **KotlinCrypto `org.kotlincrypto.hash:blake2`
  `0.8.0`** (Apache-2.0), fijado en el catalogo. Apollo **no** se anade en este bloque y
  `bip32-ed25519` tampoco; el valor de Apollo (Ed25519-BIP32) se reserva para 1.6 / 1.10. La API
  publica es neutral respecto al backend, asi que un bloque posterior puede adoptar Apollo sin
  tocar esta superficie. Detalle en ADR-0008 §8.
- Tests en `crypto/commonTest` con solo los vectores citados de 1.5b-pre, copiados verbatim y sin
  generar digests: Blake2b-224 contra la payment credential de CIP-19 (leida estructuralmente del
  address citado via `:core` `Address.parse`) y Blake2b-256 contra los dos goldens de conformance
  de IntersectMBO/plutus. Tests estructurales de `HashDigest` (copia defensiva en construccion y en
  lectura, `toString` estructural, igualdad por contenido, `InvalidDigestLength`).
- Verificacion: `./gradlew :crypto:jvmTest :crypto:testAndroidHostTest
  :crypto:compileKotlinIosSimulatorArm64 :core:jvmTest` — todos BUILD SUCCESSFUL.

Checkpoint Android:

- Pantalla de diagnostico que ejecute checks de vectores conocidos y muestre resultado
  sin usar claves reales.

### 1.6 Mnemonic / Seed / Key Derivation

Implementar creacion/restauracion de wallet de prueba.

Objetivo:

- Resolver BIP-39 / CIP-3 segun la decision tomada.
- Implementar derivacion CIP-1852.
- Modelar account / role / index.
- Mantener el tratamiento de key material acotado.
- Evitar persistencia definitiva hasta decidir el modelo.

Checkpoint Android:

- Crear o restaurar una wallet de prueba y mostrar una primera direccion testnet derivada.

### 1.7 Address Generation

Generar direcciones Shelley desde claves derivadas.

Objetivo:

- Crear payment credential y stake credential desde claves.
- Generar base address testnet.
- Producir Bech32.
- Comprobar roundtrip con `Address.parse`.
- Definir la politica de encoding/roundtrip de direcciones si todavia no existe.

Checkpoint Android:

- Generar una direccion `addr_test` en la app y parsearla inmediatamente mostrando su
  estructura.

### 1.8 Wallet State Read-Only

Conectar wallet + provider sin construir transacciones todavia.

Objetivo:

- Mostrar direccion generada.
- Consultar UTxOs para esa direccion.
- Mostrar balance ADA de prueba.
- Permitir refresco manual.

Checkpoint Android:

- Recibir ADA de faucet/preprod en la direccion generada y ver balance/UTxOs en la app.

### 1.9 Transaction Builder Minimal

Construir una transaccion ADA simple.

Objetivo:

- Seleccionar inputs.
- Crear output destino.
- Calcular change.
- Calcular fee.
- Incluir parametros minimos de validez si aplican.
- Generar el cuerpo de transaccion / CBOR necesario para firma futura.

Checkpoint Android:

- Introducir direccion destino + cantidad, construir un borrador de transaccion y ver un
  resumen antes de firmar.

### 1.10 Transaction Signing

Firmar localmente una transaccion testnet/preprod.

Objetivo:

- Usar solo claves de prueba.
- Firmar el cuerpo de transaccion.
- Producir witness / transaccion firmada segun el formato elegido.
- Mantener tests con vectores oficiales o referencias verificadas cuando existan.

Checkpoint Android:

- Construir y firmar una transaccion, mostrando tx id o CBOR firmado sin enviarlo aun.

### 1.11 Submit Transaction

Enviar la transaccion firmada a preprod.

Objetivo:

- Implementar submit via provider.
- Manejar errores de submit.
- Mostrar tx id o error comprensible.
- Opcionalmente permitir polling simple o link externo.

Checkpoint Android:

- Enviar una transaccion preprod desde la app y ver un resultado aceptado o un error
  explicable.

### 1.12 Phase 1 Closure / MVP Review

Cerrar Phase 1 con una revision del flujo completo.

Objetivo:

- Verificar que el flujo Android completo funciona en preprod.
- Confirmar tests y docs actualizados.
- Confirmar que no se ha mezclado UI dentro de `:core`.
- Documentar limitaciones conocidas.
- Definir el siguiente alcance.

Checkpoint Android:

- Demo completa: crear/restaurar wallet de prueba, ver direccion, recibir ADA de prueba,
  consultar UTxOs, construir, firmar y enviar una transaccion.

## Checkpoints Android obligatorios

Abrir la app Android y comprobar funcionalidad despues de:

- `1.2`: playground parseando direcciones.
- `1.3`: consulta read-only de UTxOs.
- `1.6`: wallet de prueba genera material derivado.
- `1.7`: direccion testnet generada y parseada.
- `1.8`: balance/UTxOs visibles.
- `1.9`: borrador de transaccion visible.
- `1.10`: transaccion firmada visible.
- `1.11`: transaccion enviada a preprod.

## Trabajo diferido o condicionado

- Byron/Base58 address support sigue separado de Phase 1 salvo decision explicita.
- Address raw/hex constructors requieren politica de encoding/roundtrip.
- Native assets pueden quedar fuera del primer MVP si el scope se aprieta.
- Persistencia de wallet puede empezar simple o quedar para otro bloque, pero no debe
  improvisarse junto con signing.
- Providers adicionales (Koios, Maestro, Ogmios, Kupo) quedan despues del primer provider.

## Siguiente paso

`1.1`, `1.2`, `1.3a` (interfaz + modelos + mock + Playground en `:provider`), `1.3b-pre`
(`Address.bech32` en `:core`), `1.3b` (`:provider-blockfrost`: `BlockfrostChainQueryProvider`
con Ktor + kotlinx-serialization, mapeo a modelos neutrales, toggle live en el Playground y
ADR-0007), `1.4` (Crypto Evaluation And Module Decision, solo docs; ADR-0008) y `1.5a` (spike de
compatibilidad, **PASS**) estan completos. `1.5a` confirmo que el candidato provisional
(Apollo 1.8.8 + `bip32-ed25519` 2.3.0) resuelve y compila en Android + JVM + iosSimulatorArm64
bajo Kotlin 2.4.0 (ADR-0008 §6); no se comprometio ninguna dependencia al build (el modulo scratch
se descarto). `1.5b-pre` (gate de vectores, solo docs) esta hecho y **pasa para ambos tamanos**:
Blake2b-224 fijado con CIP-19 y Blake2b-256 fijado con los goldens de conformance de Plutus
(`IntersectMBO/plutus` @`5e18824e`, Apache-2.0; ADR-0008 §7). `1.5b` esta **completo**: se creo
`:crypto` y se cablearon Blake2b-224/256 detras de `Hashing`. Al cablear se comprobo que Apollo
1.8.8 no incluye Blake2b, asi que el backend solo-hashing es KotlinCrypto
`org.kotlincrypto.hash:blake2` `0.8.0` (Apollo y `bip32-ed25519` no se anaden en este bloque; se
reservan para 1.6 / 1.10; ADR-0008 §8). El siguiente paso es `1.6` (mnemonic / seed / derivacion
de claves). No hay wallet, tx ni signing todavia.

