plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "br.edu.unicatolica.vetfarmaco"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // Identificador do app no aparelho (https://developer.android.com/studio/build/application-id.html).
        applicationId = "br.edu.unicatolica.vetfarmaco"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    buildTypes {
        release {
            // TODO: Add your own signing config for the release build.
            // Signing with the debug keys for now, so `flutter run --release` works.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}

// APK de release com nome legível: VetFarmaco-<versão>.apk, ao lado do app-release.apk
// (que a ferramenta do Flutter continua procurando), em build/app/outputs/flutter-apk/.
// Tarefa simples com doLast, como a do plugin do Flutter: não declara a pasta como saída.
val copiarApkRelease by tasks.registering {
    val versao = "${flutter.versionName}"
    val origem = layout.buildDirectory.file("outputs/apk/release/app-release.apk")
    val destino = layout.buildDirectory.file("outputs/flutter-apk/VetFarmaco-$versao.apk")
    doLast {
        origem.get().asFile.copyTo(destino.get().asFile, overwrite = true)
    }
}

afterEvaluate {
    tasks.named("assembleRelease") { finalizedBy(copiarApkRelease) }
}
