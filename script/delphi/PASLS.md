# Проверенный языковой сервер Free Pascal

Сервер `pasls` собран и проверен с Free Pascal 3.2.2 на macOS ARM64,
Ubuntu 24.04 ARM64 и Linux x86_64. Тест запускает настоящий процесс сервера:
инициализация, открытие корректного исходника, переход к определению,
автодополнение, синтаксическая ошибка, очистка диагностики после исправления
и штатное завершение. Это проверка протокола сервера. Отдельно в интерфейсе
Zed на Linux ARM64 проверен переход к определению через pasls.

Для Linux x86_64 опубликован
[успешный запуск CI](https://github.com/ghost-raven1/zed-delphi/actions/runs/41709650819)
с архивом, исходниками, лицензиями, сведениями о сборке и контрольными суммами.
Относительные пути запуска проверены после переноса в папку с пробелами.
Архив не включает компилятор: установите Free Pascal 3.2.2, базовые модули
и FCL отдельно. Рецепт сборки в репозитории:
`script/delphi/linux/build_pasls.py`.

Базовые Linux-пакеты используют следующие исходники без локальных изменений:

| Компонент                                                             | Ревизия исходников                                           |
| --------------------------------------------------------------------- | ------------------------------------------------------------ |
| [pasls](https://github.com/genericptr/pascal-language-server)         | `818f6330b721ed5c89d1fd8f66186f11b7b242b4`                   |
| [Lazarus](https://gitlab.com/freepascal.org/lazarus/lazarus)          | `9d15c73c91a1545be50bee02b27bd3b43f9d90e8` (`lazarus_4_0`)   |
| [Исходники Free Pascal](https://gitlab.com/freepascal.org/fpc/source) | `0d122c49534b480be9284c21bd60b53d99904346` (`release_3_2_2`) |

Локальная проверочная установка macOS находится в
`$HOME/.local/share/zed-delphi/toolchains/pasls/`. Файл `installation.json`
содержит ревизии и выбранные папки исходников, компилятор и команду сборки.
Скрипт `$HOME/.local/bin/pasls` подставляет пути к соответствующим исходникам,
если вызывающий процесс явно не задал `PP`, `FPCDIR` или `LAZARUSDIR`.
Исходники сохранены, поскольку CodeTools использует их при работе.
Для локального LCL-проекта macOS установлен [патч проверки LFM](pasls-patches/README.md)
и добавлены полные исходники Lazarus 4.8. `installation.json` содержит хеш патча,
бинарника и отдельную ревизию исходников Lazarus для работы сервера.

Из Lazarus выбраны `components/codetools`, `components/lazutils`, `components/jcf2`.
Исходники Free Pascal включают `rtl`, `packages/fcl-base`, `packages/fcl-json`.
Это минимальный набор базового пакета. Если проект зависит от других пакетов, добавьте их исходники или настройте
соответствующие пути CodeTools. Установка графической среды Lazarus не требуется.

Для пересборки с этими исходниками выполните команду из папки `source`
локальной установки macOS:

```sh
LAZARUSDIR="$HOME/.local/share/zed-delphi/toolchains/pasls/lazarus" \
FPC=/opt/homebrew/bin/fpc bash src/build_fpc.sh aarch64-darwin
```

Скрипт исходного проекта создаёт `dist/aarch64-darwin/pasls`. Для других платформ
нужен соответствующий компилятор и явно выбранная цель. Этот бинарный файл macOS
не предназначен для Windows или Linux.

Для проекта FPC выберите `pasls`. В примере замените путь к исполняемому файлу
на абсолютный путь к вашему скрипту запуска.

Встроенный адаптер по умолчанию включает проверку синтаксиса, публикацию
диагностики и режим Delphi (`-Mdelphi`). Параметры инициализации проекта могут
их переопределить: например, для ObjFPC задайте `fpcOptions: ["-Mobjfpc"]`.
Пример явно указывает значения для воспроизводимой настройки внешних клиентов.
В тестовом исходнике намеренно нет директивы `{$mode}`: режим берётся
из параметров инициализации.

```json
{
  "languages": { "Delphi": { "language_servers": ["pasls"] } },
  "lsp": {
    "pasls": {
      "binary": { "path": "/absolute/path/to/.local/bin/pasls" },
      "initialization_options": {
        "checkSyntax": true,
        "publishDiagnostics": true,
        "fpcOptions": ["-Mdelphi"]
      }
    }
  }
}
```

Запустите проверку настоящего сервера из корня форка:

```sh
python3 script/delphi/tests/smoke_pasls.py \
  --pasls "$HOME/.local/bin/pasls" \
  --compiler /opt/homebrew/bin/fpc \
  --fpc-source "$HOME/.local/share/zed-delphi/toolchains/pasls/fpc-source" \
  --lazarus-source "$HOME/.local/share/zed-delphi/toolchains/pasls/lazarus"
```

Тест создаёт временный проект и ограничивает время ожидания ответов. Успешный
результат содержит `initialize`, `definition`, `completion`,
`diagnostics_and_recovery` со значением `passed` и `shutdown_exit_code: 0`.

Эта ревизия pasls ожидает `clientInfo` при инициализации и отклоняет явный
JSON `null` в параметрах завершения. При обычном запуске Zed передаёт сведения
о клиенте и опускает параметры без значения, поэтому обходная правка адаптера
не понадобилась. Эти результаты не подтверждают совместимость с Embarcadero
DelphiLSP или работу сервера на Windows.
