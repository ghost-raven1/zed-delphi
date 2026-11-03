# Lazarus LCL на macOS ARM64

Проверен Lazarus 4.8, FPC 3.2.2, Cocoa и CodeLLDB 1.12.3 на macOS 27 ARM64.
Пример `../examples/lcl_demo` собирается, показывает форму, обрабатывает кнопку,
останавливается в обработчике на breakpoint, показывает переменные `20` и `22`,
после шага получает `42` и завершается с кодом 0. Отдельно проверены реальное
нажатие кнопки мышью и изменение надписи формы. Это проверка компилятора,
LCL и DAP; она сама по себе не подтверждает интерфейс отладки Zed.

## Инструменты

Нужны установленный FPC (`brew install fpc`), Git, Python 3 и Xcode.
Исходники берутся из официального репозитория Lazarus. Версия закреплена:

```sh
git clone --depth 1 --branch lazarus_4_8 \
  https://gitlab.com/freepascal.org/lazarus/lazarus.git "$HOME/.local/share/zed-delphi/toolchains/lazarus-4.8"
git -C "$HOME/.local/share/zed-delphi/toolchains/lazarus-4.8" rev-parse HEAD
# 62c14a4d18c81f222127d42ce9b89b922c63fcbf
make -C "$HOME/.local/share/zed-delphi/toolchains/lazarus-4.8" lazbuild lcl \
  LCL_PLATFORM=cocoa FPC=/opt/homebrew/bin/fpc
```

На проверенной машине новый Apple `ld` завершал сборку Cocoa ошибкой
`malformed method list atom ... cocoawsextctrls.o`. Для FPC 3.2.2 используется
`ld-classic` из установленного Xcode 26.1. Глобальный `xcode-select` и системный
`fpc.cfg` не меняются. Это обход несовместимости; Apple помечает этот линковщик
устаревшим. Если в выбранном Xcode нет `ld-classic`, скрипт остановится.

```sh
python3 script/delphi/macos/configure_lazarus.py \
  --source-dir "$HOME/.local/share/zed-delphi/toolchains/lazarus-4.8" \
  --fpc /opt/homebrew/bin/fpc \
  --classic-linker-dir /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin \
  --output-dir "$HOME/.local/share/zed-delphi/toolchains/lazarus-cocoa"
```

Выходная папка должна быть новой. В ней создаются `lazbuild`, `fpc-cocoa`,
изолированная конфигурация пакетов и `toolchain.json`. Можно указать этот
`lazbuild` абсолютным путём в задаче Zed или добавить папку в `PATH`.
Без `--classic-linker-dir` используется обычный линковщик выбранного FPC.

## Повторная проверка

```sh
python3 script/delphi/tests/smoke_lcl.py \
  --fixture script/delphi/examples/lcl_demo \
  --lazbuild "$HOME/.local/share/zed-delphi/toolchains/lazarus-cocoa/lazbuild" \
  --codelldb /path/to/codelldb/extension/adapter/codelldb \
  --widgetset cocoa --output /path/to/new-verification-directory
```

Сохраняются журнал сборки/запуска, полный DAP-обмен и `result.json`. Отладчик
проверяет строки исходника и значения переменных, а не только код завершения.
Проект копируется в папку с кириллицей и пробелами. Для ручного запуска соберите
`LclDemo.lpi` этим же `lazbuild --widgetset=cocoa --build-mode=Debug` и запустите
полученный `LclDemo` без `--smoke-test`: окно останется открытым до кнопки Close.

Визуальный дизайнер форм остаётся функцией Lazarus. Пример не доказывает
совместимость произвольных сторонних компонентов, VCL или FireMonkey.
