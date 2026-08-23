# Kardano SDK Quickstart

This guide runs the sample Playground in its default mock mode. It uses deterministic local
sample data and does not contact a Cardano network.

## Prerequisites

- JDK required by the repository Gradle wrapper.
- Android Studio or IntelliJ IDEA for Android development.
- Xcode on macOS when running the iOS host application.

## Run the desktop Playground

From the repository root:

```bash
./gradlew :desktopApp:run
```

The Playground opens on a **Welcome** screen that explains, in plain language, what the guided
demo does. Select **Start the demo** to begin.

## Follow the mock flow

The demo walks through one step at a time; each step has a single button and a plain-language
result. Leave the provider in its default **mock** mode (the "Advanced: connect to a test
network" disclosure, collapsed by default, is only needed for live preprod — see below).

1. Select **Create the test wallet**, then **Continue**.
2. Select **Check the balance**, then **Continue**.
3. Select **Prepare the payment**, then **Continue**.
4. Select **Approve the payment**, then **Continue**.
5. Select **Send the payment**, then **See the summary**.

The mock contains deterministic ADA-only sample UTxOs, so the first four steps complete without a
network request. The last step honestly reports **"Nothing was sent — and that's the honest
answer"**: this demo runs offline, so there is no network to send to, and the SDK says so rather
than imitating a network acceptance. The closing **Summary** screen recaps what actually happened
and offers **Run the demo again**.

The wallet behind this demo is a cited public test fixture. The UI does not display its mnemonic,
seed, or raw private-key material. Signing accepts only that fixture (recognized by its published
payment-credential fingerprint) and only a testnet ADA-only draft; a different valid mnemonic or
a mainnet-built draft is rejected. Every step also has an optional "Technical details" toggle
(collapsed by default) showing the underlying hashes, fees, draft network/scope, and raw values
for anyone who wants them.

## Run Android

Build an Android debug APK:

```bash
./gradlew :androidApp:assembleDebug
```

Open the project in Android Studio, select an emulator or device, and run `androidApp`.

## Run iOS

Open `iosApp` in Xcode and run the iOS host application on a simulator or device supported by the
local Xcode installation.

## Optional: live Blockfrost preprod mode

The Playground can query and submit only to Blockfrost preprod. Before enabling live mode:

1. On the **Demo** screen, open the collapsed **"Advanced: connect to a test network"**
   disclosure.
2. Create a Blockfrost preprod project id in your own Blockfrost account.
3. Enter the project id in the masked field. It stays in session memory (`PlaygroundState` plus
   an in-memory factory cache key used only to reuse or drop the live Blockfrost client). It is
   never shown, saved, or logged. Changing the id or turning live mode off drops that cache.
4. Use only test ADA and test addresses.

The switch alone does not activate network requests. Until the project id is non-blank, the
Advanced panel reports that configuration is incomplete and the Playground continues using the
offline mock.

Live mode queries the fixture-derived testnet address. The current Phase 1 flow is ADA-only and
fixture-scoped. It does not support mainnet, imported wallets, user-supplied mnemonics, or
native-asset transactions.

## Verify the repository

Run the focused shared Playground checks:

```bash
./gradlew :shared:jvmTest :shared:testAndroidHostTest :shared:compileKotlinIosArm64
```

For the full target/test guidance, see [TESTING.md](TESTING.md).
