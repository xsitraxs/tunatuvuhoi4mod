# Геральдические эмблемы фокусов Тувы

Полный набор: **36 из 36** подключены. Все фокусы используют предметные иллюстрации на геральдических основах.

## Готовые исходники

| Фокус | Исходник |
|---|---|
| `TT_center_of_asia` | `center_of_asia_source.png` |
| `TT_the_great_khural` | `the_great_khural_source.png` |
| `TT_red_yurt` | `red_yurt_gemini_source.png` |
| `TT_the_soviet_arsenal` | `the_soviet_arsenal_source.png` |
| `TT_the_siberian_military_district` | `the_siberian_military_district_source.png` |
| `TT_the_red_banner_over_asia` | `the_red_banner_over_asia_source.png` |
| `TT_form_central_asian_ssr` | `form_central_asian_ssr_source.png` |
| `TT_the_battle_for_manchuria` | `the_battle_for_manchuria_source.png` |
| `TT_tuvan_renaissance` | `tuvan_renaissance_source.png` |
| `TT_the_second_khanate` | `the_second_khanate_source.png` |
| `TT_the_great_khan` | `the_great_khan_source.png` |
| `TT_the_empire_of_the_steppe` | `the_empire_of_the_steppe_source.png` |
| `TT_first_five_year_plan` | `first_five_year_plan_source.png` |
| `TT_collective_herds` | `collective_herds_source.png` |
| `TT_kyzyl_industries` | `industry_source.png` |
| `TT_mineral_prospecting` | `mineral_prospecting_source.png` |
| `TT_the_kyzyl_railroad` | `the_kyzyl_railroad_source.png` |
| `TT_the_yenisei_dam` | `the_yenisei_dam_source.png` |
| `TT_the_golden_hoard` | `the_golden_hoard_source.png` |
| `TT_the_peoples_army` | `the_peoples_army_source.png` |
| `TT_cavalry_of_the_steppe` | `cavalry_source.png` |
| `TT_soviet_advisors` | `soviet_advisors_source.png` |
| `TT_mountain_warfare` | `mountain_warfare_source.png` |
| `TT_the_tuvan_air_force` | `the_tuvan_air_force_source.png` |
| `TT_total_mobilization` | `total_mobilization_source.png` |
| `TT_infantry_and_artillery` | `infantry_and_artillery_source.png` |
| `TT_tanks_of_the_steppe` | `tanks_of_the_steppe_source.png` |
| `TT_wings_of_the_steppe` | `wings_of_the_steppe_source.png` |
| `TT_bombers_over_siberia` | `bombers_over_siberia_source.png` |
| `TT_the_yenisei_flotilla` | `the_yenisei_flotilla_source.png` |
| `TT_kyzyl_naval_school` | `kyzyl_naval_school_source.png` |
| `TT_the_pacific_fleet` | `the_pacific_fleet_source.png` |
| `TT_claims_on_the_steppe` | `claims_on_the_steppe_source.png` |
| `TT_the_mongolian_question` | `the_mongolian_question_source.png` |
| `TT_greater_tuva` | `greater_tuva_source.png` |
| `TT_the_siberian_gambit` | `the_siberian_gambit_source.png` |

## Происхождение

`red_yurt_gemini_source.png` предоставлен пользователем из Gemini (вложение `image-8.png`). Остальные активные исходники созданы инструментом генерации с этой юртой как стилевым ориентиром для новой партии. Это AI-assisted иллюстрации, не заказанные у художника ручные работы и не исторические фотографии. Ванильные текстуры и чужие моды не использовались.

Новые исходники сохранены с длинной стороной 768 px: этого достаточно для игровых 95×85, без тяжёлых мастер-файлов в репозитории. Ранние три исходника сохранены в прежнем размере. `red_yurt_source.png` — неактивный ранний эскиз юрты, в игру не попадает.

## Текущая геральдическая композиция

Шесть оригинальных AI-generated основ сохранены в `emblems/` (PNG до 640×640):

| Основа | Назначение |
|---|---|
| `political.png` | Солнечные лучи, тёмная бирюзовая подложка, лавр и степной орнамент |
| `industry.png` | Клёпаная стальная пластина, шестерня и колос |
| `army.png` | Тёмно-красный щит, скрещённые винтовки и лавр |
| `air.png` | Синяя подложка, серебряные крылья и бронзовый солнечный веер |
| `naval.png` | Морская подложка, канат, якорь и красные складки ткани |
| `territory.png` | Угловатая пластина, бронзовые лучи и бирюзовая ткань |

Это собственные сгенерированные основы, не скопированные из Kaiserreich, LooterGFX
или ресурсных паков. Примеры сообщества изучались только как визуальный ориентир;
их ассеты в мод не переносились.

`EMBLEM_GROUPS` назначает каждому фокусу ровно одну структуру. `heraldic_icon()`
собирает изображение с 4× сглаживанием: цветная металлическая основа, тёмный рельефный
контур и предмет. Предмет извлекается из сохранённого исходника в полном разрешении,
получает умеренное усиление контраста и резкости и затем уменьшается вместе с эмблемой.
`keyed_art()` очищает розовую подложку и кеширует подготовленные слои на время сборки.
Никакой сети или повторной генерации при пересборке не требуется.

Границы DDS прозрачны, normal/shine-привязки не меняются. Ранние пейзажные сцены в
`backgrounds/` сохранены как неактивный эксперимент и больше не используются сборкой.

## Подготовка и пересборка

Розовый фон в исходниках технический: он удаляется, а цвет краевых пикселей
очищается до уменьшения. Результат — 36 DDS 95×85 с альфой. Явные манифесты
`PAINTED_SOURCES` и `EMBLEM_GROUPS` исключают неполные сборки; старого SVG-fallback нет.
Зависимость сборки — Pillow 13.0.0; валидаторы используют только стандартную библиотеку.

Из корня репозитория, с зависимостями из README:

```sh
python docs/generate_focus_icons.py
python docs/icon_studies/build_preview.py
python docs/icon_studies/check_painted_icons.py
python docs/validate_mod.py
python docs/validate_mod.py --mutation-test
```

`../focus_icon_style_study.png` показывает готовые игровые DDS при увеличении ×2 и в масштабе 1:1; браузер может масштабировать лист целиком. `../focus_icons_preview.png` показывает компактный обзор всех 36 текущих эмблем. `../red_yurt_gemini_preview.png` — ранняя отдельная проба юрты без пейзажа, ×3/1:1.

Исходники не нужны игре, `docs/**` исключён из экспорта. Проверка непосредственно в HOI4 ещё нужна.

## Завершение набора

Последняя партия: `TT_the_mongolian_question` (монгольское седло и дипломатический свиток),
`TT_greater_tuva` (карта, церемониальная печать и бирюзовый вымпел),
`TT_the_siberian_gambit` (шахматный конь, карта и снежные вершины).
Все 36 имеют отдельные исходники и normal/shine-привязки; fallback на медальоны отсутствует.
