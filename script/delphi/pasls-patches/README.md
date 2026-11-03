# Проверка ресурсов LCL в pasls на macOS

Патч применяется к `genericptr/pascal-language-server` на ревизии
`818f6330b721ed5c89d1fd8f66186f11b7b242b4`. Он проверен с FPC 3.2.2 на macOS ARM64.
Для сборки pasls использованы CodeTools/JCF/LazUtils из Lazarus 4.0,
ревизия `9d15c73c91a1545be50bee02b27bd3b43f9d90e8`.
Для работы с проектом LCL установлены полные исходники Lazarus 4.8,
ревизия `62c14a4d18c81f222127d42ce9b89b922c63fcbf`.

## Исправленная ошибка

Строгий синтаксический анализатор pasls отвергал корректную директиву
`{$R *.lfm}` с ошибкой `No support for resources of type "lfm"`.
В scanner добавлен обработчик только для `.lfm`. Он проверяет текстовый
ресурс через `Classes.ObjectTextToBinary`, не создавая компоненты и не
запуская код формы. Поиск и проверка наличия файла остаются в штатном scanner.

Проверка синтаксиса и публикация диагностики остаются включёнными. Ошибки Pascal,
повреждённые формы и отсутствующие файлы ресурсов продолжают давать диагностику.
Это не полная проверка свойств и классов компонентов: их корректность проверяет
сборка/запуск Lazarus. Ошибки ресурса публикуются в контексте включающего Pascal-файла;
точная позиция ошибки LFM доступна в тексте сообщения, а не как отдельный LFM diagnostic.

## Применение и сборка

Из папки чистых исходников pasls на указанной ревизии:

```sh
git apply --check /path/to/zed/script/delphi/pasls-patches/lfm-resource-validation.patch
git apply /path/to/zed/script/delphi/pasls-patches/lfm-resource-validation.patch
LAZARUSDIR=/path/to/lazarus-4.0 FPC=/opt/homebrew/bin/fpc \
  bash src/build_fpc.sh aarch64-darwin
```

Результат — `dist/aarch64-darwin/pasls`. При запуске нужны переменные `PP`
(компилятор), `FPCDIR` (исходники FPC) и `LAZARUSDIR` (полные исходники Lazarus 4.8).
Одна папка CodeTools без `lcl` недостаточна для переходов к типам `TForm`/`TButton`.

В `.zed/settings.json` самого LCL-проекта задайте параметры инициализации.
Замените `/ABS/lazarus` и путь проекта абсолютными путями; JSON не раскрывает `$HOME`.

```json
{
  "lsp": {
    "pasls": {
      "initialization_options": {
        "checkSyntax": true,
        "publishDiagnostics": true,
        "program": "/ABS/project/LclDemo.lpr",
        "fpcOptions": [
          "-Mobjfpc",
          "-dLCL",
          "-dLCLcocoa",
          "-Fi/ABS/lazarus/lcl/include",
          "-Fu/ABS/lazarus/lcl",
          "-Fu/ABS/lazarus/lcl/widgetset",
          "-Fu/ABS/lazarus/components/lazutils",
          "-Fu/ABS/lazarus/components/freetype",
          "-Fu/ABS/lazarus/packager/registration",
          "-Fu/ABS/lazarus/lcl/interfaces",
          "-Fu/ABS/lazarus/lcl/interfaces/cocoa"
        ]
      }
    }
  }
}
```

После замены бинарника или настройки перезапустите языковой сервер в Zed.
Эта конфигурация относится к Cocoa. Linux-пакет pasls из прежнего CI остаётся
неизменённым: перенос патча на Linux требует отдельной сборки и проверки.

## Настоящая протокольная проверка

Из корня форка:

```sh
python3 script/delphi/pasls-patches/smoke_lcl_pasls.py \
  --pasls /path/to/patched/pasls --compiler /opt/homebrew/bin/fpc \
  --fpc-source /path/to/fpc-source --lazarus-source /path/to/lazarus-4.8 \
  --fixture script/delphi/examples/lcl_demo --output /path/to/new-result-directory
```

Тест использует настоящий сервер и копию проекта. Проверяются переход `TForm`
в `forms.pp`, переход из реализации обработчика к объявлению, автодополнение,
отсутствие ошибок в корректной форме, ошибка Pascal и восстановление, повреждённый
LFM и восстановление, отсутствующий LFM и восстановление, штатное завершение.
Сохраняются `result.json`, все уведомления и stderr сервера. Дополнительно пройден
обычный `script/delphi/tests/smoke_pasls.py`, включая диагностику и её очистку.
