# This .spec config file tells Buildozer an app's requirements for being built.

[app]
p4a.source_dir = ./python-for-android
title = Focus Buddy
package.name = focusbuddy
package.domain = org.test
source.dir = .
source.include_exts = py,png,jpg,jpeg,webp,kv,atlas,wav,mp3,json
version = 0.1

# p4a manages hostpython3 automatically; pyjnius provides the jnius module.
requirements = python3==3.11.9, hostpython3==3.11.9, kivy==2.3.0, pillow, plyer, pyjnius

orientation = portrait
fullscreen = 0

android.permissions = READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, READ_MEDIA_IMAGES, ACCESS_NOTIFICATION_POLICY
android.api = 33
android.ndk = 25c
android.ndk_api = 24
android.ndk_path = /usr/local/lib/android/sdk/ndk/26.3.11579264
android.sdk_path = /usr/local/lib/android/sdk
android.archs = arm64-v8a
android.copy_libs = 1
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
