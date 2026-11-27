plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "app.jarvis.assistant"
    compileSdk = 35

    defaultConfig {
        applicationId = "app.jarvis.assistant"
        minSdk = 29
        targetSdk = 34
        versionCode = 60
        versionName = "Mark LX"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("com.squareup.okhttp3:okhttp:4.12.0")

    // Unit tests run on a plain JVM, where Android's org.json is only a stub.
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
