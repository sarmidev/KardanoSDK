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

Crear una pantalla o seccion de pruebas en Android para invocar funcionalidades del SDK.

Objetivo:

- Tener un sitio visible donde probar el SDK durante toda Phase 1.
- Parsear direcciones `addr_test` / `stake_test`.
- Mostrar `network`, `AddressType`, credentials y pointer cuando aplique.
- Probar errores tipados de direccion de forma comprensible.
- Opcionalmente exponer checks simples de Hex, Bech32 y CBOR.

Checkpoint Android:

- Abrir la app, pegar una direccion testnet y ver el resultado estructural en pantalla.

### 1.3 Provider Read-Only Boundary

Definir y probar la capa de consulta de red antes de crear wallets.

Objetivo:

- Definir una interfaz de provider para consultas read-only.
- Consultar UTxOs de una direccion.
- Consultar parametros necesarios para transacciones futuras, si se decide incluirlos ya.
- Modelar errores de red con tipos claros.
- Implementar el primer provider de preprod o una capa mock/stub si se decide por fases.

Checkpoint Android:

- Pegar una direccion preprod y ver sus UTxOs o un estado "sin UTxOs" desde la app.

### 1.4 Crypto Evaluation And Module Decision

Bloque de decision/evaluacion, basado en ADR-0004.

Objetivo:

- Evaluar librerias/bindings concretos para los algoritmos que Phase 1 necesita.
- Decidir si se crea `:crypto` ahora o si se empieza con un paquete aislado.
- Registrar decisiones en ADR-0004 o en un ADR nuevo si hace falta.
- No implementar wallet completa en este bloque.

Checkpoint Android:

- Mantener la app compilando. Este bloque desbloquea los siguientes, aunque no tenga una
  pantalla funcional nueva.

### 1.5 Crypto Primitives Needed For Wallet

Implementar solo las primitivas necesarias para el MVP de wallet, siguiendo ADR-0004.

Objetivo:

- Implementar wrappers/bindings de los algoritmos elegidos.
- Cubrirlos con vectores oficiales.
- Mantener errores tipados.
- Evitar exponer bytes mutables internos.
- No firmar transacciones todavia si se puede separar.

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

`1.1 Phase 1 Scope And Architecture Plan` esta completo (ver "Decisiones del Bloque 1.1" y
ADR-0005). El siguiente paso es `1.2 Android SDK Playground`: crear el playground en Android
para parsear direcciones `addr_test` / `stake_test` y ejercitar el SDK existente (Hex,
Bech32, CBOR), manteniendo `:core` libre de UI. Este es el primer bloque de implementacion de
Phase 1; no implica crypto, wallet, provider ni transacciones.

