plugins {
    id("org.jetbrains.kotlin.jvm") version "2.2.0"
    id("org.jetbrains.intellij.platform") version "2.11.0"
}

group = providers.gradleProperty("pluginGroup").get()
version = providers.gradleProperty("pluginVersion").get()

repositories {
    mavenCentral()
    intellijPlatform {
        defaultRepositories()
    }
}

kotlin {
    jvmToolchain(21)
}

dependencies {
    intellijPlatform {
        pycharmCommunity(providers.gradleProperty("platformVersion").get())
        bundledPlugin("PythonCore")
    }
}

intellijPlatform {
    pluginConfiguration {
        id = "com.literalenum.pycharm"
        name = providers.gradleProperty("pluginName").get()
        version = providers.gradleProperty("pluginVersion").get()
        description = "Makes LiteralEnum subclasses dual-natured: Literal unions in annotations, normal classes in value positions."
        ideaVersion {
            sinceBuild = "252"
            untilBuild = "252.*"
        }
    }
}

tasks {
    wrapper {
        gradleVersion = "8.13"
    }
}
