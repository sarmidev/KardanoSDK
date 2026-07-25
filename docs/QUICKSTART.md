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

The Playground opens on its overview screen. Choose **Try SDK** to open the guided flow.

## Follow the mock flow

1. Leave the provider in **Mock** mode.
2. Select **Create test wallet**.
3. Select **Check available test ADA**.
4. Select **Prepare a transaction**.
5. Select **Sign it locally**.
6. Select **Send it to preprod**.

The mock contains deterministic ADA-only sample UTxOs, so the Wallet, Funds, Build, and Sign
steps complete without a network request. The final mock submission reports that the mock does not
submit transactions. It does not imitate a network acceptance.

The wallet behind this demo is a cited public test fixture. The UI does not display its mnemonic,
seed, or raw private-key material.

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

1. Create a Blockfrost preprod project id in your own Blockfrost account.
2. Enter the project id in the Playground; it remains in non-persistent UI state.
3. Use only test ADA and test addresses.

Live mode queries the fixture-derived testnet address. The current Phase 1 flow is ADA-only and
fixture-scoped. It does not support mainnet, imported wallets, user-supplied mnemonics, or
native-asset transactions.

## Verify the repository

Run the focused shared Playground checks:

```bash
./gradlew :shared:jvmTest :shared:testAndroidHostTest :shared:compileKotlinIosArm64
```

For the full target/test guidance, see [TESTING.md](TESTING.md).
