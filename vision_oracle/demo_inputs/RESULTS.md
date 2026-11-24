# C3 demo screens (verified through the app's service)

Load each image in HEART > Screen inspection > Choose screenshot > Inspect screenshot. For 06, also attach `06_overlap_synthetic_layout.json` under Advanced options > Add layout file to show the element name. (05's labelled defect region spans most of the screen, so its matched element, the navigation bar background, is not meaningful; demo 05 without the layout.) Keep 'Extra tile views' off.

| File | Layout | Expected | App result | Score | Element | Correct | Point at |
|---|---|---|---|---|---|---|---|
| 01_overlap_team_names.jpg | - | defect / component_overlap | defect / component_overlap | 0.82 | - | yes | team names and labels drawn over each other |
| 02_overlap_title.jpg | - | defect / component_overlap | defect / component_overlap | 0.67 | - | yes | 'Classes' title drawn over the description |
| 03_null_text.jpg | - | defect / data_binding_null | defect / data_binding_null | 0.93 | - | yes | result shows the word 'null' |
| 04_missing_icons.jpg | - | defect / missing_component | defect / missing_component | 0.89 | - | yes | category icons not rendered |
| 05_missing_widget_synthetic.jpg | 05_missing_widget_synthetic_layout.json | defect / missing_component | defect / missing_component | 0.92 | android:id/navigationBarBackground | yes | grey placeholder replaces a widget |
| 06_overlap_synthetic.jpg | 06_overlap_synthetic_layout.json | defect / component_overlap | defect / component_overlap | 0.64 | com.mevikings.mapwhosyourdaddy:id/wbdesc | yes | widget pasted over another |
| 07_clean_owleye.jpg | - | clean / none | clean / none | 0.36 | - | yes | normal screen, not flagged |
| 08_clean_rico.jpg | - | clean / none | clean / none | 0.36 | - | yes | normal screen, not flagged |
| 09_known_miss_truncation.jpg | - | defect / text_truncation | clean / none | 0.53 | - | NO | thin clipped text: the model misses it (honest limitation) |

These are selected screens that show behaviour. They are not the accuracy. Quote accuracy only from the held-out test (AUC 0.75, F1 0.69, precision 61%, recall 79%, 316 screens). Boxes are approximate.