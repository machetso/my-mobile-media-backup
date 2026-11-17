// The phone app has the SAME version as the desktop program (user request 2026-11-17):
// read from phonebackup/__init__.py; versionCode = a.b.c.d → a*1000000 + b*10000 + c*100 + d
val desktopVersion: String = Regex("""__version__\s*=\s*"([^"]+)"""")
    .find(rootProject.file("../phonebackup/__init__.py").readText())!!.groupValues[1]
val desktopVersionCode: Int = (desktopVersion.split(".").map { it.toInt() } + listOf(0, 0, 0, 0))
    .take(4).let { (a, b, c, d) -> a * 1000000 + b * 10000 + c * 100 + d }

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "io.github.machetso.mediabackup"
    // interface languages: i18n/<code>.json at the top of the repository (shared with the desktop)
    sourceSets["main"].assets.srcDir("../../i18n")
    compileSdk {
        version = release(37) { minorApiLevel = 2 }
    }

    defaultConfig {
        applicationId = "io.github.machetso.mediabackup"
        minSdk = 30          // Android 11 - same as wireless debugging
        targetSdk = 36
        versionCode = desktopVersionCode     // 0.9.8.4 → 90804
        versionName = desktopVersion
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildFeatures { compose = true }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"))
            signingConfig = signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2026.09.00")
    implementation(composeBom)
    implementation("androidx.core:core-ktx:1.19.1")
    implementation("androidx.activity:activity-compose:1.13.0")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20250517")
}
