# Приёмка Lazarus LCL на Linux x86_64

Workflow `Lazarus LCL Linux x86_64 acceptance` проверяет один и тот же проект
`script/delphi/examples/lcl_demo` в Ubuntu 24.04 и в официальном Astra Linux
UBI 1.8. На сервере GitHub используется x86_64 без эмуляции процессора.
Контейнер получает разрешение `SYS_PTRACE` для дочернего процесса отладчика.

Проверка включает сборку `lazbuild` с GTK2, запуск приложения в Xvfb,
остановку CodeLLDB в обработчике кнопки, значения переменных и пошаговое
выполнение. После этого приложение запускается отдельно: тест находит
реально отображённое окно, нажимает кнопку мышью, проверяет надпись
`Result: 42` и закрывает окно кнопкой `Close` с кодом завершения 0.
Путь проекта содержит кириллицу и пробелы.

Для локального повторения на машине Linux x86_64:

```sh
mkdir -p verification-lcl
docker run --rm --platform linux/amd64 \
  --cap-add SYS_PTRACE --security-opt seccomp=unconfined \
  --mount "type=bind,source=$PWD,target=/repo,readonly" \
  --mount "type=bind,source=$PWD/verification-lcl,target=/verification" \
  registry.astralinux.ru/library/astra/ubi18:latest \
  bash /repo/script/delphi/linux/lcl-acceptance.sh
```

Каталог результата должен быть новым: повторный запуск не перезаписывает
предыдущую приёмку. Требуется доступ к репозиториям пакетов ОС и GitHub.
Образ Astra взят из [официальной документации](https://docs.astralinux.ru/latest/guide/virtual/docker/).
Workflow сохраняет digest образа, `/etc/os-release`, версии установленных
пакетов, закреплённую контрольную сумму CodeLLDB 1.12.3, журнал,
результаты отладки и снимки окна.

Это проверка библиотек и программ пользовательского пространства Astra UBI.
Она не проверяет рабочий стол Fly, защищённый режим, политики конкретной
установки Astra или её ядро: ядро предоставляет хост GitHub. Этот workflow
не собирает Zed и не заменяет приёмку его упакованного интерфейса.
Успешная проверка стандартного проекта LCL не подтверждает совместимость
всех сторонних компонентов Lazarus и проектов VCL/FireMonkey.
