# Organisation identifier conflicts

Generated 2026-09-13 by `make orgattrs`.

A matricule fiscal and a registre-de-commerce number are hard
identifiers: a firm has one of each. An organisation node carrying two
is therefore a defect, and there are two quite different defects here.

* **A few values clustered around one** — OCR damage. This corpus
  confuses 4 and 6 routinely, so `1518656` and `1518456` are one
  registration read twice. The node is fine; the value needs a vote.
* **Many values with nothing in common** — an organisation-resolution
  **merge**. Two or more firms have been collapsed into one node, and
  every tie on that node is suspect.

Nothing else in the pipeline can detect the second kind, because a
merge looks exactly like a well-corroborated match: both names really
do appear beside the same kind of clause. That is what makes a hard
identifier worth recording even when it is never used as a variable.

## What this found

| kind | organisations affected |
| --- | --- |
| matricule_fiscal | 2148 of 79431 carrying one (3%) |
| registre_commerce | 2058 of 33702 carrying one (6%) |

Of 4206 conflicts over **3405 organisations**, **3100 read as merges** and 1106 as OCR damage. A conflict is one (organisation, identifier kind) pair, so a node with a bad matricule *and* a bad RC number counts twice here and once in that organisation total.

The distribution is not what a metadata problem looks like. The worst node, **SOCIETE M**, carries **154 distinct matricule fiscal values** over 374 observations, with its modal value accounting for only 3% of them. That is not one registration misread; it is a generic name fragment that every firm beginning with those words resolves onto.

**So the dominant failure in organisation resolution is the generic-name merge, not fuzzy-match noise.** A node like that does not degrade a variable — it fabricates a hub, and any centrality computed over it is meaningless. Treat the merge rows below as a blocklist: exclude those nodes, or split them, before using organisation-level structure.

Classifying these on the distance between the two closest values was the first attempt and it inverted the signal: among hundreds of numbers some pair is always one character apart, so the worst merges were labelled OCR. The test is instead whether the values cluster around the modal one.

## Conflicts, worst merges first

| organisation | identifier | values | modal share | reads as | most-observed values |
| --- | --- | --- | --- | --- | --- |
| SOCIETE M | matricule_fiscal | 154 | 3% | merge | `1387182Z` (10), `1293190F` (8), `992132D` (8), `1214095T` (7), `1283124P` (7), … +149 more |
| SOCIETE DE PROMOTION IMMOBILIERE | matricule_fiscal | 118 | 6% | merge | `754848J` (33), `570983W` (21), `719356S` (20), `833596Z` (13), `958310H` (13), … +113 more |
| SOCIETE DE PROMOTION IMMOBILIERE | registre_commerce | 113 | 4% | merge | `B110002001` (21), `B151252000` (18), `B130991997` (17), `B2425942007` (14), `B1117961997` (12), … +108 more |
| SMAG | matricule_fiscal | 73 | 7% | merge | `953145R` (10), `1143469K` (5), `1298734N` (4), `1211768A` (3), `1242010D` (3), … +68 more |
| SOCIETE MUTUELLE DE BASE DES SERVICES AGRICOLES EL-FALAH | matricule_fiscal | 66 | 5% | merge | `1205726B` (5), `776V` (4), `1008698Q` (3), `1025179T` (3), `1874029E` (3), … +61 more |
| ARC EN CIEL | matricule_fiscal | 64 | 8% | merge | `1244934A` (11), `1357169L` (7), `775642L` (7), `1112658S` (5), `1065233D` (4), … +59 more |
| BB | matricule_fiscal | 62 | 5% | merge | `958835J` (6), `975694M` (6), `1161062R` (5), `1472588Y` (5), `1173553W` (3), … +57 more |
| TUNISIE FONDERIE | matricule_fiscal | 57 | 7% | merge | `929047A` (8), `1147103Y` (3), `1504471M` (3), `1544955A` (3), `939323G` (3), … +52 more |
| SOCIETE BAYA | matricule_fiscal | 48 | 5% | merge | `1152664M` (5), `1270226B` (5), `1453310L` (4), `1276556T` (3), `1281396E` (3), … +43 more |
| SOCIETE EL-BARAKA | matricule_fiscal | 45 | 9% | merge | `349694Z` (8), `943515F` (5), `952921E` (5), `1279563F` (4), `1320541P` (4), … +40 more |
| SOCIETE EVENT | matricule_fiscal | 44 | 12% | merge | `816663R` (15), `795140D` (10), `1477001D` (6), `1481965E` (5), `1113398W` (4), … +39 more |
| LINK | matricule_fiscal | 43 | 20% | merge | `1001375S` (32), `1214663E` (15), `904223Q` (12), `1029460J` (9), `1226388T` (9), … +38 more |
| SOCIETE ADEM | matricule_fiscal | 42 | 6% | merge | `1314988F` (5), `1240148N` (4), `1280773F` (4), `889656X` (4), `1319477H` (3), … +37 more |
| SOCIETE UNIQUE | matricule_fiscal | 42 | 22% | merge | `947693D` (28), `2309D` (11), `431699A` (7), `1348069G` (5), `965502G` (4), … +37 more |
| LE FUTURE | matricule_fiscal | 40 | 19% | merge | `1021337X` (22), `960004W` (10), `1323377J` (7), `1261503C` (5), `1361978S` (5), … +35 more |
| SOCIETE MUTUELLE DE BASE DES SERVICES AGRICOLES EL-FALAH | registre_commerce | 40 | 8% | merge | `B24119452011` (5), `B2443662006` (5), `B162971997` (4), `B2472992007` (3), `01149032017` (2), … +35 more |
| SAAD | matricule_fiscal | 39 | 6% | merge | `1145981F` (5), `779285C` (5), `1192202F` (4), `1195307C` (4), `1537449T` (4), … +34 more |
| SOCIETE INES | matricule_fiscal | 39 | 10% | merge | `433713J` (10), `548462S` (9), `913925R` (5), `496362B` (4), `1117976B` (3), … +34 more |
| SOCIETE MULTISERVICES | matricule_fiscal | 37 | 11% | merge | `760474L` (9), `1024399A` (6), `1028994G` (4), `1604206C` (4), `1425684H` (3), … +32 more |
| SOCIETE CIVILE IMMOBILIERE | matricule_fiscal | 36 | 11% | merge | `1196071F` (12), `1205895T` (10), `796816F` (8), `1312254N` (6), `1455350D` (5), … +31 more |
| SOCIETE JAWHARA | matricule_fiscal | 36 | 11% | merge | `496428C` (11), `918740F` (8), `738541Y` (7), `1238899C` (6), `1113076E` (5), … +31 more |
| EMNA | matricule_fiscal | 35 | 11% | merge | `1104866C` (10), `983196V` (7), `1350906Q` (5), `418040A` (4), `520275W` (4), … +30 more |
| PHENIX | matricule_fiscal | 35 | 10% | merge | `840725G` (9), `510648A` (8), `920386D` (7), `1261734R` (6), `982181H` (5), … +30 more |
| SPEED | matricule_fiscal | 35 | 10% | merge | `1489982Q` (8), `809748G` (6), `1135020G` (4), `1068883X` (3), `1147532R` (3), … +30 more |
| SOCIETE ENTREPRISE TRABELSI | matricule_fiscal | 34 | 15% | merge | `624954M` (11), `1294912W` (5), `584166R` (5), `1110303H` (3), `625305M` (3), … +29 more |
| SOCIETE IRIS | matricule_fiscal | 34 | 6% | merge | `1377953P` (4), `956958L` (4), `1039951E` (3), `1059199G` (3), `1096655T` (3), … +29 more |
| CARTHAGO SA | matricule_fiscal | 33 | 22% | merge | `35760Z` (22), `1016555X` (12), `644548M` (5), `875861C` (5), `1089748F` (4), … +28 more |
| SOCIETE DE MISE EN VALEUR ET DE DEVELOPPEMENT AGRICOLE | matricule_fiscal | 33 | 8% | merge | `587620F` (13), `736406H` (13), `1361054E` (10), `349464L` (9), `1053615A` (8), … +28 more |
| ARC EN CIEL | registre_commerce | 32 | 20% | merge | `B131681997` (12), `B2077192012` (6), `B1118861996` (3), `B2430602012` (3), `B0255312005` (2), … +27 more |
| LE MOTEUR | matricule_fiscal | 32 | 10% | merge | `1130552K` (10), `1483726Z` (8), `836992W` (8), `1283427C` (6), `1183353V` (5), … +27 more |
| PREMIUM | matricule_fiscal | 32 | 9% | merge | `1249877F` (7), `1274758T` (5), `1028602A` (4), `1176662N` (4), `1426711X` (4), … +27 more |
| SOCIETE YOSR | matricule_fiscal | 32 | 20% | merge | `587499Z` (13), `1110053J` (6), `1050714P` (5), `1448814Y` (5), `1237692J` (4), … +27 more |
| SOCIETE DE MISE EN VALEUR ET DE DEVELOPPEMENT AGRICOLE | registre_commerce | 31 | 14% | merge | `B2469412008` (16), `B11291` (9), `B112912003` (9), `B131041997` (8), `B154371997` (7), … +26 more |
| MODA | matricule_fiscal | 30 | 8% | merge | `1219980M` (6), `1177044W` (5), `1003502P` (4), `1203618P` (4), `1309829G` (4), … +25 more |
| AMANA | matricule_fiscal | 29 | 9% | merge | `1437026R` (6), `504321Q` (5), `1208857A` (4), `10761959W` (3), `1292857Y` (3), … +24 more |
| SOCIETE ALFA | matricule_fiscal | 29 | 17% | merge | `901039E` (11), `544581G` (4), `1091356N` (3), `1107960M` (3), `1206459F` (3), … +24 more |
| SOCIETE CIVILE IMMOBILIERE | registre_commerce | 29 | 14% | merge | `B07118722011` (10), `B0289792013` (8), `B158341996` (7), `C0155972008` (6), `C0351752007` (6), … +24 more |
| SOCIETE ASMA | matricule_fiscal | 28 | 14% | merge | `1414847Z` (7), `778929M` (4), `1437955B` (3), `1490554P` (3), `1123535R` (2), … +23 more |
| SOCIETE LE COIN | matricule_fiscal | 28 | 23% | merge | `1231067M` (18), `1125332Q` (5), `1223649H` (4), `1386252R` (4), `795077P` (4), … +23 more |
| SOCIETE ZIED | matricule_fiscal | 28 | 12% | merge | `1411373X` (7), `1333716N` (4), `1090575T` (3), `1488292Q` (3), `1587249P` (3), … +23 more |
| SOCIETE ¨PALM | matricule_fiscal | 27 | 9% | merge | `1065132Z` (7), `1028282E` (6), `1573563Z` (6), `1574595M` (5), `1146870D` (4), … +22 more |
| ENGINEERING D'AFFAIRES ET CONSULTING | matricule_fiscal | 26 | 12% | merge | `1196984Q` (6), `1315920N` (3), `1030512V` (2), `1125323P` (2), `1125387G` (2), … +21 more |
| MAYA | matricule_fiscal | 26 | 10% | merge | `1031522B` (6), `1212195N` (4), `1222536V` (4), `1278452V` (4), `1327035F` (4), … +21 more |
| SOCIETE ANIS | matricule_fiscal | 26 | 13% | merge | `797092X` (8), `1485476J` (4), `1021546E` (3), `1189749N` (3), `1296386E` (3), … +21 more |
| SOCIETE EL-YOSR | matricule_fiscal | 26 | 14% | merge | `1110053J` (9), `1307276L` (4), `1336448A` (4), `615235K` (4), `1091147F` (3), … +21 more |
| SOCIETE GLOBE | matricule_fiscal | 26 | 9% | merge | `1115642X` (6), `323694M` (6), `1263303E` (5), `774310N` (4), `988427M` (4), … +21 more |
| SOCIETE NOUR | matricule_fiscal | 26 | 14% | merge | `620582L` (10), `1220246D` (7), `349539N` (7), `1301601C` (6), `1276669C` (4), … +21 more |
| CENTRAL | matricule_fiscal | 25 | 20% | merge | `1287385C` (16), `986737Q` (9), `1184329Z` (5), `9247M` (5), `1218362L` (4), … +20 more |
| LA ROSA | matricule_fiscal | 25 | 11% | merge | `1322794T` (6), `1524836H` (4), `1543744L` (4), `1489835E` (3), `1154Y` (2), … +20 more |
| PNEU | matricule_fiscal | 25 | 14% | merge | `1145573S` (10), `2172E` (9), `283866Q` (9), `1078824Q` (4), `1161611Z` (4), … +20 more |
| SELECTION | matricule_fiscal | 25 | 10% | merge | `991762A` (7), `1246678M` (6), `1014887G` (4), `1290285Z` (4), `1325703L` (4), … +20 more |
| EL WIFEK | matricule_fiscal | 24 | 12% | merge | `438610Z` (6), `784622H` (6), `1236696J` (4), `504352Y` (4), `1237481Z` (3), … +19 more |
| SICAV ENTREPRISE | registre_commerce | 24 | 16% | merge | `B186251996` (20), `B11574` (17), `B115741997` (16), `B014377` (11), `B1157641997` (9), … +19 more |
| SOCIETE HAMZA | matricule_fiscal | 24 | 9% | merge | `1222016Z` (4), `1253571T` (3), `1324193G` (3), `34461L` (3), `1188249S` (2), … +19 more |
| SOCIETE MABROUK | matricule_fiscal | 24 | 31% | merge | `580188F` (25), `1177809T` (6), `1165483C` (4), `385454N` (4), `966567E` (4), … +19 more |
| CHIC | matricule_fiscal | 23 | 10% | merge | `1056547T` (5), `897753T` (4), `1389757B` (3), `1398472R` (3), `1598457F` (3), … +18 more |
| SOCIETE YASMINE | matricule_fiscal | 23 | 17% | merge | `588259N` (7), `1339595Z` (5), `1507929P` (3), `876898W` (3), `921899E` (3), … +18 more |
| STEP | matricule_fiscal | 23 | 14% | merge | `1251519F` (9), `1398104T` (5), `488136W` (4), `999308Q` (4), `1184719K` (3), … +18 more |
| EL FAOUZ | matricule_fiscal | 22 | 18% | merge | `1017737F` (11), `963770S` (8), `858402E` (6), `612789D` (4), `1089161H` (3), … +17 more |
| GENERAL TRAVAUX DE CONSTRUCTION GTC | matricule_fiscal | 22 | 15% | merge | `1355310N` (7), `1458286B` (4), `1029981F` (2), `1037412X` (2), `1083764I` (2), … +17 more |
| LES HORIZONS | matricule_fiscal | 22 | 8% | merge | `1556071K` (4), `1122777E` (3), `1128494X` (3), `1286689M` (3), `1334844A` (3), … +17 more |
| SOCIETE DE NUTRITION | matricule_fiscal | 22 | 28% | merge | `842437K` (21), `1113857C` (7), `737785N` (7), `2992K` (5), `1474874K` (4), … +17 more |
| ME CONSULTANTS | matricule_fiscal | 21 | 24% | merge | `761845Y` (24), `980692T` (21), `1299448P` (7), `775137Y` (7), `1302629V` (5), … +16 more |
| ENTREPRISE EL-AMEN | matricule_fiscal | 20 | 24% | merge | `718584Z` (18), `1176119T` (16), `1042279V` (12), `1063164Z` (6), `1005432B` (2), … +15 more |
| SOCIETE LE LABO | matricule_fiscal | 20 | 13% | merge | `1121630F` (7), `583889S` (7), `1100532P` (4), `766861V` (4), `1267726S` (3), … +15 more |
| SOMAFRIP | matricule_fiscal | 20 | 22% | merge | `1386476G` (9), `1084894T` (2), `1086513Z` (2), `1223640Y` (2), `12526715S` (2), … +15 more |
| ERRAHMA | matricule_fiscal | 19 | 64% | merge | `884195R` (68), `635620B` (10), `1025491Z` (3), `1029874D` (3), `1109154X` (2), … +14 more |
| ETABLISSEMENT GHORBEL | matricule_fiscal | 19 | 9% | merge | `1068472F` (3), `1415931Y` (3), `1035641A` (2), `1400355K` (2), `1410851C` (2), … +14 more |
| GLOBAL SERVICES | matricule_fiscal | 19 | 29% | merge | `926133J` (14), `1003086V` (6), `1325021Q` (3), `1392746Y` (3), `1202376L` (2), … +14 more |
| SOCIETE REAL ESTATE | matricule_fiscal | 19 | 15% | merge | `1104105Q` (8), `1179884P` (6), `1010815X` (5), `1227214A` (5), `1204037C` (2), … +14 more |
| SOCIETE SALMA | matricule_fiscal | 19 | 28% | merge | `612787B` (12), `1403839P` (3), `1031764T` (2), `1078477R` (2), `1371958T` (2), … +14 more |
| SOCIETE YESMINE | matricule_fiscal | 19 | 19% | merge | `944007F` (11), `1233140M` (6), `946327D` (4), `1084688P` (3), `1208232W` (3), … +14 more |
| VENUS | matricule_fiscal | 19 | 21% | merge | `875973K` (12), `1351470M` (8), `1052590E` (4), `1387982A` (4), `1028604C` (3), … +14 more |
| CHAMS | matricule_fiscal | 18 | 15% | merge | `1158536F` (7), `9233F` (4), `1117131L` (3), `1154597C` (3), `1214738G` (3), … +13 more |
| EL HOUDA | matricule_fiscal | 18 | 20% | merge | `644485P` (11), `1013539J` (6), `1000837Y` (4), `635896E` (4), `928674T` (4), … +13 more |
| JUNIOR | matricule_fiscal | 18 | 20% | merge | `937275H` (11), `1025883M` (6), `975311G` (6), `1080559N` (3), `1295925F` (3), … +13 more |
| LINK | registre_commerce | 18 | 21% | merge | `B025042005` (12), `B25159372011` (12), `B2427862007` (9), `B2484592007` (4), `B2532822012` (3), … +13 more |
| SOCIETE GENERALE DE MENUISERIE SOGEM | matricule_fiscal | 18 | 17% | merge | `789331W` (9), `968189G` (9), `420354M` (7), `1353970M` (3), `36847K` (3), … +13 more |
| SOCIETE SINDBAD | matricule_fiscal | 18 | 17% | merge | `1464437L` (8), `1047255H` (5), `33420X` (4), `83564Q` (4), `1075736D` (3), … +13 more |
| SOCIETE START | matricule_fiscal | 18 | 22% | merge | `1142207J` (10), `32307S` (4), `1319887Y` (3), `1372155T` (3), `1424426L` (3), … +13 more |
| AZIZA | matricule_fiscal | 17 | 20% | merge | `968444G` (8), `1117381D` (3), `1265313Q` (3), `1488982L` (3), `1148974N` (2), … +12 more |
| CARTHAGO SA | registre_commerce | 17 | 17% | merge | `B2422622004` (7), `B2455392007` (7), `B0116822006` (3), `B110532003` (3), `B14462003` (3), … +12 more |
| EL FATH | matricule_fiscal | 17 | 14% | merge | `1337376F` (5), `1329327Z` (4), `1207994E` (3), `1211370F` (2), `1282808H` (2), … +12 more |
| NESRINE | matricule_fiscal | 17 | 10% | merge | `1360328H` (3), `1526961W` (3), `1217391M` (2), `1266529K` (2), `1330114D` (2), … +12 more |
| PANORAMA | matricule_fiscal | 17 | 12% | merge | `296329M` (4), `905539N` (4), `1337403Q` (2), `1452580D` (2), `1453850L` (2), … +12 more |
| SERA | matricule_fiscal | 17 | 28% | merge | `794807W` (19), `1032633M` (9), `1094354Z` (5), `1350321V` (5), `578639R` (5), … +12 more |
| SOCIETE AMEUR | registre_commerce | 17 | 25% | merge | `B170131997` (14), `B247502008` (14), `B0251892004` (7), `B115371996` (3), `B25178872011` (3), … +12 more |
| SOCIETE AMINA | matricule_fiscal | 17 | 22% | merge | `760439H` (13), `1189215L` (8), `1441290L` (5), `1350590Q` (4), `708427F` (4), … +12 more |
| SOCIETE ENTREPRISE TRABELSI | registre_commerce | 17 | 15% | merge | `B0770222013` (6), `B166081998` (6), `B2510972004` (5), `B1119891998` (4), `B148002000` (3), … +12 more |
| SOCIETE EZDIHAR | matricule_fiscal | 17 | 15% | merge | `1173444R` (6), `1008211C` (4), `743724M` (4), `1197374Y` (3), `1383415E` (3), … +12 more |
| SOCIETE INTERACTIVE | matricule_fiscal | 17 | 21% | merge | `911130D` (10), `601887V` (7), `985048R` (4), `136242A` (3), `989017B` (3), … +12 more |
| SOCIETE SOLTANA | matricule_fiscal | 17 | 12% | merge | `1421009J` (5), `24120L` (5), `1316992K` (3), `1335434P` (3), `1003017F` (2), … +12 more |
| LA TUNISIENNE | matricule_fiscal | 16 | 18% | merge | `536917P` (12), `710611Z` (9), `1332369K` (8), `15175B` (7), `25612G` (7), … +11 more |
| PROMED | matricule_fiscal | 16 | 18% | merge | `1099803A` (7), `1167779A` (4), `710820G` (4), `1160864Q` (3), `916085N` (3), … +11 more |
| SERA | registre_commerce | 16 | 16% | merge | `B131332009` (7), `B2440972012` (6), `B197031996` (5), `143222002` (3), `B0131702009` (3), … +11 more |
| SOCIETE AMEUR | matricule_fiscal | 16 | 22% | merge | `1037211P` (9), `1218909A` (6), `539369W` (3), `647979W` (3), `882091A` (3), … +11 more |
| SOCIETE EL-KHADRA | matricule_fiscal | 16 | 21% | merge | `1094798A` (13), `6473H` (12), `47376A` (8), `1276176K` (4), `2301V` (4), … +11 more |
| SOCIETE VITAL | matricule_fiscal | 16 | 14% | merge | `822354X` (6), `748728N` (5), `712802N` (4), `979190J` (4), `1214216J` (3), … +11 more |
| COMPETENCES+ | matricule_fiscal | 15 | 13% | merge | `1266563M` (5), `984221G` (4), `1225655P` (3), `1225756T` (3), `1281155N` (3), … +10 more |
| LA FONDATION | matricule_fiscal | 15 | 26% | merge | `835118E` (14), `587880A` (6), `1064381L` (5), `1264087W` (4), `1403618C` (4), … +10 more |
| PHENIX | registre_commerce | 15 | 22% | merge | `B0631872004` (9), `B2931995` (8), `B2462372006` (5), `B31125882012` (3), `B0313032008` (2), … +10 more |
| SICAV ENTREPRISE | matricule_fiscal | 15 | 20% | merge | `1055155B` (13), `1566945S` (9), `492474R` (7), `492473Q` (6), `770729W` (6), … +10 more |
| SOCIETE ASMA | registre_commerce | 15 | 14% | merge | `B021802004` (4), `B161702001` (4), `B03109972009` (3), `B0127932016` (2), `B0217302005` (2), … +10 more |
| SPEED | registre_commerce | 15 | 20% | merge | `B2434302007` (13), `B123382002` (7), `B01258392016` (6), `B147352002` (6), `B2445292005` (6), … +10 more |
| COSMOS | matricule_fiscal | 14 | 15% | merge | `1013852Q` (5), `1347030L` (4), `1227369V` (3), `1389678D` (3), `1504826V` (3), … +9 more |
| GALLAND ETABLISSEMENT STABLE | matricule_fiscal | 14 | 38% | merge | `968975B` (14), `1194038W` (5), `1297377H` (3), `1422176D` (3), `765122K` (3), … +9 more |
| LE FUTURE | registre_commerce | 14 | 32% | merge | `A1314371998` (22), `B02158572012` (9), `B0268932007` (6), `B01141302009` (5), `B0228062006` (5), … +9 more |
| LE RESEAU | matricule_fiscal | 14 | 18% | merge | `1406193L` (10), `1012896Z` (9), `893431K` (7), `539151D` (5), `1106189W` (4), … +9 more |
| RANIM | matricule_fiscal | 14 | 22% | merge | `1351380L` (7), `1116658K` (3), `1105069J` (2), `1137437N` (2), `1210708H` (2), … +9 more |
| SOCIETE CHAIMA | matricule_fiscal | 14 | 20% | merge | `1048157L` (9), `1042834A` (7), `1077374F` (7), `1042634A` (4), `1261612G` (4), … +9 more |
| SOCIETE EL-BARAKA | registre_commerce | 14 | 27% | merge | `B163411996` (8), `B0421852013` (4), `193312000` (3), `B00755262006` (2), `B0174732008` (2), … +9 more |
| SOCIETE SIRINE | matricule_fiscal | 14 | 22% | merge | `543776M` (9), `1197390Y` (6), `833559T` (5), `1593035P` (4), `1206035J` (2), … +9 more |
| SOCIETE ZIED | registre_commerce | 14 | 14% | merge | `B126312000` (3), `B2521792007` (3), `B0127782004` (2), `B0722812004` (2), `B117302003` (2), … +9 more |
| CESAR | matricule_fiscal | 13 | 14% | merge | `1161879C` (3), `1108533A` (2), `1277770C` (2), `13781301K` (2), `1408088V` (2), … +8 more |
| EL AMEL | matricule_fiscal | 13 | 27% | merge | `1014246C` (9), `1105745Y` (4), `609751N` (4), `1290219N` (2), `1392916Y` (2), … +8 more |
| EL AMEL | registre_commerce | 13 | 33% | merge | `B1112591998` (11), `B0350862007` (5), `B140191998` (4), `B181321998` (3), `B114322002` (2), … +8 more |
| INTERNATIONAL PROD SIGN COMPANY TUNISIA | matricule_fiscal | 13 | 31% | merge | `1142790M` (8), `1410775H` (3), `1074561T` (2), `1102146R` (2), `1169223A` (2), … +8 more |
| LA PRECISION MECANIQUE | matricule_fiscal | 13 | 14% | merge | `1109331W` (4), `967819K` (4), `10420Y` (3), `1033802Q` (2), `1267351F` (2), … +8 more |
| LA SOURCE | matricule_fiscal | 13 | 14% | merge | `1390345A` (3), `1021787W` (2), `1029705L` (2), `1139131F` (2), `1286076M` (2), … +8 more |
| LA TUNISIENNE | registre_commerce | 13 | 25% | merge | `B116451996` (14), `B1106841996` (13), `B4481996` (12), `B153661999` (5), `B11645` (3), … +8 more |
| SAAD | registre_commerce | 13 | 21% | merge | `B0376762010` (5), `B2451272011` (4), `B01212932017` (2), `B13211998` (2), `B19225352017` (2), … +8 more |
| SOCIETE ALMA | matricule_fiscal | 13 | 17% | merge | `1539560A` (6), `1113716P` (5), `1139174S` (5), `1190459X` (4), `1366061A` (3), … +8 more |
| SOCIETE EL-MAJD | matricule_fiscal | 13 | 30% | merge | `1427173X` (8), `1077297K` (3), `1131592Y` (2), `1143920H` (2), `1181034Y` (2), … +8 more |
| SOCIETE EL-WIFAK | matricule_fiscal | 13 | 12% | merge | `283777Q` (3), `4414611N` (3), `74526033N` (3), `1092222D` (2), `1141112Y` (2), … +8 more |
| SOCIETE HAIFA | matricule_fiscal | 13 | 25% | merge | `1130386P` (15), `798547M` (12), `870190N` (8), `939231D` (7), `1605717B` (4), … +8 more |
| SOCIETE LE COIN | registre_commerce | 13 | 23% | merge | `B2418192009` (7), `B01175522014` (4), `B25116352011` (4), `D3115232011` (4), `B01187022016` (2), … +8 more |
| SOCIETE LE LABO | registre_commerce | 13 | 18% | merge | `B115761999` (6), `B0225602005` (5), `B2414322011` (5), `B131682003` (3), `A0123122004` (2), … +8 more |
| SOCIETE MABROUK | registre_commerce | 13 | 17% | merge | `B0914372010` (7), `B0112452009` (6), `B25204972010` (6), `B2528782007` (6), `B01119922009` (3), … +8 more |
| AL BADR | matricule_fiscal | 12 | 23% | merge | `977730G` (6), `1045669T` (3), `1386890S` (3), `789285H` (3), `1511088B` (2), … +7 more |
| BRAVO | matricule_fiscal | 12 | 29% | merge | `858784J` (18), `1179783K` (13), `1147350M` (7), `1335480W` (5), `811575Z` (5), … +7 more |
| CENTRAL | registre_commerce | 12 | 26% | merge | `B0146672013` (11), `B014082007` (7), `B110861996` (5), `B216191302010` (5), `B17646` (3), … +7 more |
| EL WIFEK | registre_commerce | 12 | 35% | merge | `B129781996` (8), `B0514372009` (2), `B09231232015` (2), `B26138392010` (2), `B9150152012` (2), … +7 more |
| EMNA | registre_commerce | 12 | 31% | merge | `B01109232009` (10), `B0265732006` (5), `B1122491997` (4), `B0821262006` (3), `B136632002` (2), … +7 more |
| LES HORIZONS | registre_commerce | 12 | 14% | merge | `B10165992015` (4), `B01175962009` (3), `B0329022014` (3), `B0412592004` (3), `B15144772013` (3), … +7 more |
| MODA | registre_commerce | 12 | 16% | merge | `B03117592011` (4), `B2417642007` (4), `B24181922009` (3), `A1188671998` (2), `B0240342015` (2), … +7 more |
| SELECTION | registre_commerce | 12 | 20% | merge | `D3125697` (6), `B24219442011` (5), `B0185562012` (4), `B2452082007` (4), `B0813122005` (2), … +7 more |
| SOCIETE AMANI | matricule_fiscal | 12 | 21% | merge | `1455335E` (5), `515524K` (4), `1053292B` (2), `1274815K` (2), `1424340F` (2), … +7 more |
| SOCIETE EL-IZDIHAR | matricule_fiscal | 12 | 12% | merge | `1082967K` (2), `1241490E` (2), `1438665Y` (2), `1443284X` (2), `1473454N` (1), … +7 more |
| SOCIETE ETABLISSEMENT TRIKI | matricule_fiscal | 12 | 32% | merge | `953213L` (8), `1085881S` (2), `1131439P` (2), `1158872V` (2), `1347391K` (2), … +7 more |
| SOCIETE M | registre_commerce | 12 | 25% | merge | `B0731462015` (7), `9171042013` (3), `B0171042013` (3), `B2761102011` (3), `B01239262013` (2), … +7 more |
| SOCIETE SINDBAD | registre_commerce | 12 | 17% | merge | `B128232008` (5), `B141821997` (4), `B0151462005` (3), `B141021997` (3), `B171181997` (3), … +7 more |
| SOCIETE UNIQUE | registre_commerce | 12 | 38% | merge | `B16242002` (12), `B0317982005` (7), `B1116671996` (2), `B1547832005` (2), `B518912014` (2), … +7 more |
| SOMAC | matricule_fiscal | 12 | 20% | merge | `1048884M` (5), `1173161H` (3), `1184741H` (3), `894317N` (3), `1154275L` (2), … +7 more |
| AMANA | registre_commerce | 11 | 31% | merge | `B0839012010` (9), `B0112672016` (4), `B2513182011` (4), `B0148462016` (3), `B1681992013` (3), … +6 more |
| CHAMS | registre_commerce | 11 | 18% | merge | `B2479732007` (4), `B195301997` (3), `D11637` (3), `D25512005` (3), `B1117711997` (2), … +6 more |
| DEFI | matricule_fiscal | 11 | 17% | merge | `1168147B` (4), `1549454E` (4), `1147213D` (3), `1018979C` (2), `1436206P` (2), … +6 more |
| LE PILOTE | matricule_fiscal | 11 | 22% | merge | `37603V` (6), `1603785F` (4), `1195167J` (3), `837803V` (3), `1320768H` (2), … +6 more |
| LEILA | matricule_fiscal | 11 | 25% | merge | `307285E` (7), `578841R` (6), `1134528C` (4), `1221863D` (2), `1370973N` (2), … +6 more |
| NOUR DE COMMERCE | matricule_fiscal | 11 | 22% | merge | `1011690G` (6), `1202168E` (3), `1213637Y` (2), `1223534X` (2), `1418789Z` (2), … +6 more |
| PLASTICS | matricule_fiscal | 11 | 54% | merge | `12866K` (22), `889956G` (5), `1324701E` (3), `1527846Y` (3), `1361122Z` (2), … +6 more |
| SILVER SAPHIR | matricule_fiscal | 11 | 25% | merge | `1126756R` (5), `1080189G` (2), `1157333R` (2), `1218390Q` (2), `1316506G` (2), … +6 more |
| SOCIETE ADEM | registre_commerce | 11 | 14% | merge | `B09173892013` (3), `B195422007` (3), `B197691998` (3), `B40165582015` (3), `1612662015` (2), … +6 more |
| SOCIETE AMINA | registre_commerce | 11 | 21% | merge | `B0151652006` (8), `B1154371997` (7), `B158762002` (5), `B15876202` (4), `B3135242011` (4), … +6 more |
| SOCIETE DELIVERY | matricule_fiscal | 11 | 33% | merge | `983313F` (15), `432912K` (12), `1794326Q` (6), `1139138N` (2), `1435032F` (2), … +6 more |
| SOCIETE EZZAHRA | matricule_fiscal | 11 | 22% | merge | `1392733S` (5), `356712A` (4), `1071398N` (2), `1193099F` (2), `1457726A` (2), … +6 more |
| SOCIETE HENDA | matricule_fiscal | 11 | 41% | merge | `430134G` (8), `1481224X` (2), `1556919K` (2), `44754C` (2), `981472M` (2), … +6 more |
| SOCIETE JAWHARA | registre_commerce | 11 | 30% | merge | `B1132801997` (10), `B07187442011` (5), `B092042006` (5), `B0911802006` (2), `B0912011` (2), … +6 more |
| SOCIETE NADINE + | matricule_fiscal | 11 | 31% | merge | `635831L` (8), `1121398S` (2), `1151556E` (2), `1219842C` (2), `1332594S` (2), … +6 more |
| SOCIETE SARAH | matricule_fiscal | 11 | 17% | merge | `613864B` (4), `1423521E` (3), `307159Z` (3), `125124Q` (2), `1427133N` (2), … +6 more |
| SOCIETE TUNISIENNE DE COMMERCE | matricule_fiscal | 11 | 19% | merge | `1118169F` (4), `1501412M` (3), `1286985S` (2), `1340131K` (2), `1344014Y` (2), … +6 more |
| DISCOVERY | matricule_fiscal | 10 | 18% | merge | `955323A` (4), `971451B` (4), `1124325M` (2), `1125906H` (2), `1298513B` (2), … +5 more |
| EL ALIA | matricule_fiscal | 10 | 24% | merge | `1223544Z` (8), `1226289R` (5), `1472185G` (4), `1501398H` (4), `1144359J` (3), … +5 more |
| EL HANA | matricule_fiscal | 10 | 18% | merge | `987297R` (4), `1164832Z` (3), `1170763R` (2), `1324901L` (2), `1409852F` (2), … +5 more |
| EL HOUDA | registre_commerce | 10 | 21% | merge | `B2526902007` (6), `B117391999` (5), `B17391` (4), `B195421997` (3), `B2471162008` (3), … +5 more |
| EL WAFA | matricule_fiscal | 10 | 17% | merge | `1042438A` (3), `1014358K` (2), `1229384C` (2), `1403054M` (2), `1451246M` (2), … +5 more |
| INTERNATIONAL PROD SIGN COMPANY TUNISIA | registre_commerce | 10 | 18% | merge | `B01136842015` (3), `B2489642008` (3), `801166832010` (2), `B0144732009` (2), `B2479212008` (2), … +5 more |
| KMG SERVICES | matricule_fiscal | 10 | 33% | merge | `1364584Q` (9), `1231141E` (2), `1270427J` (2), `1306352B` (2), `1321442R` (2), … +5 more |
| MAYA | registre_commerce | 10 | 18% | merge | `B192902000` (3), `B01148352010` (2), `B01208322018` (2), `B0493572007` (2), `B2045222005` (2), … +5 more |
| SOCIETE ALFA | registre_commerce | 10 | 21% | merge | `B134092000` (4), `B179131997` (4), `B2459002006` (3), `B24106062009` (2), `A09186692010` (1), … +5 more |
| SOCIETE BAYA | registre_commerce | 10 | 29% | merge | `B09206802012` (4), `B2514412004` (2), `B01203742017` (1), `B0198092010` (1), `B02144642013` (1), … +5 more |
| SOCIETE DE COMMERCE INTERNATIONAL | matricule_fiscal | 10 | 18% | merge | `1040118T` (5), `1036844P` (4), `1419272C` (4), `982996R` (4), `1221081E` (2), … +5 more |
| SOCIETE DE NUTRITION | registre_commerce | 10 | 38% | merge | `B132882003` (9), `B08253752017` (3), `B08179112016` (2), `B117812001` (2), `B15132272009` (2), … +5 more |
| SOCIETE GLOBE | registre_commerce | 10 | 24% | merge | `B1112171996` (8), `B31164402012` (5), `B2415782007` (4), `B245492007` (4), `B152392001` (3), … +5 more |
| SOCIETE IMEM | matricule_fiscal | 10 | 23% | merge | `639495H` (6), `1321429V` (5), `1040053T` (2), `1140372N` (2), `1418589S` (2), … +5 more |
| SOCIETE INES | registre_commerce | 10 | 37% | merge | `B1123611997` (10), `B170051998` (6), `B0152592005` (4), `170051998` (1), `A20173582012` (1), … +5 more |
| SOCIETE JMF | matricule_fiscal | 10 | 17% | merge | `1089766H` (3), `1020630Q` (2), `1038396V` (2), `1181281M` (2), `1372202H` (2), … +5 more |
| SOCIETE LINA | matricule_fiscal | 10 | 11% | merge | `1153592S` (2), `1187977Q` (2), `1224096A` (2), `1300655N` (2), `1364799E` (2), … +5 more |
| SOCIETE OCTOPUS | matricule_fiscal | 10 | 17% | merge | `1103781T` (3), `1164990N` (2), `1191170L` (2), `1491590Y` (2), `1495147Z` (2), … +5 more |
| TUNISIE TRAVAUX | matricule_fiscal | 10 | 18% | merge | `857921V` (6), `111269V` (5), `838552H` (4), `1112692V` (3), `1191070H` (3), … +5 more |
| AGENCE EL-AMANA IMMOBILIERE AEL | matricule_fiscal | 9 | 20% | merge | `1071452B` (3), `1182883N` (2), `1292857Y` (2), `1566999H` (2), `614853C` (2), … +4 more |
| AGORA | matricule_fiscal | 9 | 24% | merge | `985808J` (7), `1164697L` (5), `1297218S` (4), `1310651P` (3), `892401Z` (3), … +4 more |
| ARTEMIS | matricule_fiscal | 9 | 27% | merge | `1237666G` (6), `1049050E` (4), `1191969V` (3), `1213487C` (2), `1326400C` (2), … +4 more |
| BANQUE DE TUNISIE BT | registre_commerce | 9 | 43% | merge | `B140811997` (31), `B1105941996` (14), `B14081` (7), `B1163511197` (6), `B1163511997` (5), … +4 more |
| EL FAOUZ | registre_commerce | 9 | 39% | merge | `B2557942007` (11), `A164311999` (7), `B08672004` (2), `B145921997` (2), `D025942013` (2), … +4 more |
| ENGINEERING D'AFFAIRES ET CONSULTING | registre_commerce | 9 | 28% | merge | `B0762982008` (8), `B0378322011` (6), `B08239282013` (3), `B09175612013` (3), `B2427362011` (3), … +4 more |
| ENNASR | matricule_fiscal | 9 | 22% | merge | `896345B` (4), `1189435X` (3), `1221226Q` (2), `1238813P` (2), `1292864N` (2), … +4 more |
| FARAH | matricule_fiscal | 9 | 36% | merge | `38228W` (11), `843718W` (5), `1108075V` (3), `1000975H` (2), `1448520L` (2), … +4 more |
| GENERAL MAGHREB SERVICES | matricule_fiscal | 9 | 57% | merge | `900648W` (40), `764626B` (13), `901487B` (6), `1334343H` (4), `1024399A` (2), … +4 more |
| LE BON GOUT | matricule_fiscal | 9 | 25% | merge | `620509B` (5), `1312192R` (3), `1231179V` (2), `1286002S` (2), `1332750L` (2), … +4 more |
| MANUF TUNISIENNE DES SERRURES MTS | matricule_fiscal | 9 | 31% | merge | `45372W` (9), `1159808Q` (5), `1174778R` (4), `1245379Z` (4), `1459958Z` (2), … +4 more |
| PNEU | registre_commerce | 9 | 45% | merge | `B11242002` (13), `B164531998` (5), `B01217942017` (3), `B15178472010` (2), `B1589712008` (2), … +4 more |
| SOCIETE EL-AMAL | matricule_fiscal | 9 | 48% | merge | `944132K` (15), `1395085W` (5), `1013643H` (2), `1232701V` (2), `1392142Z` (2), … +4 more |
| SOCIETE EL-YOSR | registre_commerce | 9 | 29% | merge | `B27116112009` (9), `B24752008` (5), `B1339142014` (4), `B0220922016` (3), `B08212014` (3), … +4 more |
| SOCIETE ESSAADA | matricule_fiscal | 9 | 21% | merge | `449637W` (4), `881688W` (4), `10305W` (2), `1318653B` (2), `1486299P` (2), … +4 more |
| SOCIETE HENDA | registre_commerce | 9 | 30% | merge | `191521997` (5), `B154871997` (4), `B191521997` (4), `D034672006` (2), `191421997` (1), … +4 more |
| SOCIETE HOTELIERE ET TOURISTIQUE HOTEL IBN KHALDOUN | registre_commerce | 9 | 57% | merge | `B188161996` (21), `B197511996` (8), `B134841997` (2), `B111531998` (1), `B12751997` (1), … +4 more |
| SOCIETE IMMOBILIERE | matricule_fiscal | 9 | 40% | merge | `762750W` (12), `1525744J` (6), `411858G` (3), `1355558M` (2), `31459E` (2), … +4 more |
| SOCIETE IRIS | registre_commerce | 9 | 17% | merge | `B138592001` (3), `B15239912014` (3), `B248782008` (3), `19582001` (2), `B01173282013` (2), … +4 more |
| SOCIETE NOUR | registre_commerce | 9 | 26% | merge | `B150052001` (7), `B51118782013` (6), `B0421112005` (5), `B15186122009` (3), `B09126352014` (2), … +4 more |
| SOCIETE OLIVA | matricule_fiscal | 9 | 33% | merge | `1327542W` (11), `578644N` (8), `814700Y` (3), `1258632L` (2), `1397256F` (2), … +4 more |
| SOCIETE RISTORANTE ITALIANO LA PERLA NERA | matricule_fiscal | 9 | 38% | merge | `1021766Q` (10), `1096227B` (4), `1221590X` (2), `1262445P` (2), `1298591R` (2), … +4 more |
| SOCIETE SLAMA | matricule_fiscal | 9 | 23% | merge | `1202915R` (6), `1283594S` (4), `566070G` (4), `899039G` (3), `1069495S` (2), … +4 more |
| SOCIETE TAAMIR | matricule_fiscal | 9 | 30% | merge | `896331V` (7), `1058083Q` (3), `1213115M` (3), `1235254F` (2), `1354036K` (2), … +4 more |
| SOCIETE TUNISIENNE DELECTRO PORTATIF | matricule_fiscal | 9 | 33% | merge | `822993Z` (11), `889901Q` (5), `1277591B` (4), `802083G` (4), `1373454G` (3), … +4 more |
| SOCIETE TUNISIENNE DELECTRO PORTATIF | registre_commerce | 9 | 26% | merge | `B14082003` (11), `B179411996` (11), `B0939632004` (5), `B01239272012` (4), `B137282002` (4), … +4 more |
| SOCIETE YOSR | registre_commerce | 9 | 22% | merge | `B113341997` (6), `B27116112009` (6), `B0133332008` (5), `B0268982016` (3), `B01167772014` (2), … +4 more |
| TAYSIR | matricule_fiscal | 9 | 22% | merge | `1202048X` (6), `1350779C` (6), `1446999Q` (3), `1594039Y` (3), `1339609M` (2), … +4 more |
| BANQUE DE TUNISIE BT | matricule_fiscal | 8 | 47% | merge | `120H` (15), `1086260X` (5), `121J` (5), `1385594H` (2), `15094B` (2), … +3 more |
| BRAVO | registre_commerce | 8 | 29% | merge | `B27622004` (10), `B0322962010` (6), `B149962002` (5), `B13402001` (4), `B03222962010` (3), … +3 more |
| EL FATH | registre_commerce | 8 | 35% | merge | `B2640072014` (7), `B0811742014` (4), `B03149452011` (3), `C1381198` (2), `1612848201` (1), … +3 more |
| FLORENCE | matricule_fiscal | 8 | 25% | merge | `9934691G` (5), `1031730N` (3), `496239Z` (3), `583987T` (3), `1389416G` (2), … +3 more |
| GENERAL MAGHREB SERVICES | registre_commerce | 8 | 76% | merge | `B0855112004` (36), `B221452005` (7), `B24246442006` (3), `B0123152014` (2), `B0856112004` (2), … +3 more |
| L'OLIVIER BLEU DE RESTAURATION ET DE LOISIRS | matricule_fiscal | 8 | 29% | merge | `960643Y` (6), `822681K` (4), `1191422M` (3), `1210944T` (2), `1211004K` (2), … +3 more |
| LA CONFIANCE | matricule_fiscal | 8 | 15% | merge | `1141087Q` (2), `1186258K` (2), `1270640M` (2), `1352135D` (2), `1528577A` (2), … +3 more |
| LA FONDATION | registre_commerce | 8 | 44% | merge | `B123212003` (14), `B24168122012` (4), `B243052005` (4), `B0180532007` (3), `B124022001` (3), … +3 more |
| LE RESEAU | registre_commerce | 8 | 36% | merge | `B2451512007` (11), `02115312015` (10), `B0178212008` (2), `B0365002013` (2), `B1102541996` (2), … +3 more |
| MAGHREB INTERNATIONAL PUBLICITE MIP | registre_commerce | 8 | 48% | merge | `B0167672008` (19), `B19582003` (5), `B2410942004` (4), `B2510052009` (4), `B0181482008` (3), … +3 more |
| MARAM SERVICE | matricule_fiscal | 8 | 23% | merge | `1382020J` (5), `1262150B` (4), `1531233C` (4), `1076946R` (2), `1436764R` (2), … +3 more |
| MARHABA | matricule_fiscal | 8 | 24% | merge | `989509S` (6), `1091550N` (4), `1200451W` (3), `1595009W` (3), `44665C` (3), … +3 more |
| POLYMONT INGENIERIE CONSULTING | matricule_fiscal | 8 | 31% | merge | `1017005Z` (4), `1523644X` (2), `1546808Y` (2), `1234980B` (1), `1280036C` (1), … +3 more |
| POULINA | matricule_fiscal | 8 | 25% | merge | `1013461D` (6), `1025115B` (6), `2970D` (4), `1062980W` (2), `29700D` (2), … +3 more |
| PRESTIGE | matricule_fiscal | 8 | 33% | merge | `1025936H` (7), `340668H` (4), `1135848V` (2), `1379288M` (2), `1432779G` (2), … +3 more |
| ROMA | matricule_fiscal | 8 | 19% | merge | `1076157T` (3), `1149374E` (3), `1195899Q` (2), `1311543Q` (2), `1455675Y` (2), … +3 more |
| SOCIETE DE COMMERCE INTERNATIONAL | registre_commerce | 8 | 17% | merge | `B03124532013` (2), `B15177012015` (2), `B24190722011` (2), `B243782008` (2), `B0220522015` (1), … +3 more |
| SOCIETE DE MAINTENANCE EL-FERDAOUS | matricule_fiscal | 8 | 29% | merge | `925137J` (8), `1299241A` (5), `1105228F` (4), `1201600V` (3), `1309002T` (2), … +3 more |
| SOCIETE EL-ANDALOUS | matricule_fiscal | 8 | 38% | merge | `1284993J` (9), `552442S` (4), `1223538B` (2), `1453620Y` (2), `1541120Z` (2), … +3 more |
| SOCIETE EL-IZDIHAR | registre_commerce | 8 | 35% | merge | `B19251997` (6), `B0247972008` (4), `B265402009` (2), `B0143822005` (1), `B02172202016` (1), … +3 more |
| SOCIETE EVENT | registre_commerce | 8 | 37% | merge | `B158082002` (15), `B131892002` (11), `B01215832016` (3), `B0177802016` (3), `B1144011997` (3), … +3 more |
| SOCIETE GENERALE TRAVAUX | matricule_fiscal | 8 | 26% | merge | `907437R` (7), `906938E` (6), `781271R` (4), `413710V` (3), `1026315M` (2), … +3 more |
| SOCIETE HASNA | matricule_fiscal | 8 | 25% | merge | `917596M` (7), `1158996G` (5), `1433214B` (5), `1201933P` (3), `11158996G` (2), … +3 more |
| SOCIETE IMMOBILIERE | registre_commerce | 8 | 42% | merge | `B2420782004` (8), `B01158012017` (2), `B143291997` (2), `B158921996` (2), `B2420002006` (2), … +3 more |
| SOCIETE MODERNE DE BATIMENT | matricule_fiscal | 8 | 18% | merge | `1303517R` (4), `1305051L` (4), `1420980R` (4), `1495847X` (3), `999313M` (3), … +3 more |
| SOCIETE MS CONSULTING | matricule_fiscal | 8 | 19% | merge | `1319354X` (3), `1408196Y` (3), `1255148Q` (2), `1328254V` (2), `1413101G` (2), … +3 more |
| SOCIETE RIHAB | matricule_fiscal | 8 | 43% | merge | `644742M` (12), `22762H` (5), `1006590V` (2), `1197481A` (2), `1253930X` (2), … +3 more |
| SOCIETE SAMAR | matricule_fiscal | 8 | 14% | merge | `1012573G` (2), `1273275Z` (2), `1292714H` (2), `1366668C` (2), `1460649E` (2), … +3 more |
| SOCIETE TAAMIR | registre_commerce | 8 | 33% | merge | `B187191996` (8), `B0948382004` (4), `B143142002` (4), `B181791996` (3), `B201042008` (2), … +3 more |
| SOCIETE TRAVAUX ET SERVICES | matricule_fiscal | 8 | 29% | merge | `969478S` (5), `1495308Y` (4), `1106088R` (2), `1422672Q` (2), `1194584R` (1), … +3 more |
| SOCIETES ANONYMES SOCIETE TUNISIAN CONTINENTAL HOTELS TUCOTEL | matricule_fiscal | 8 | 29% | merge | `1276692B` (8), `758138B` (7), `9439T` (6), `1237132E` (2), `1408877S` (2), … +3 more |
| SOGEBAT | matricule_fiscal | 8 | 17% | merge | `134239Z` (2), `1439263M` (2), `1501115F` (2), `1564500G` (2), `104498J` (1), … +3 more |
| SOGECO | matricule_fiscal | 8 | 23% | merge | `2011M` (5), `1425086Q` (4), `1042231C` (3), `1042241E` (3), `411618R` (3), … +3 more |
| STEP | registre_commerce | 8 | 30% | merge | `B27108092012` (6), `B08167972010` (5), `B0925691007` (2), `B0925692007` (2), `B119192003` (2), … +3 more |
| AGRICO | matricule_fiscal | 7 | 21% | merge | `998159R` (3), `1136515F` (2), `1514794K` (2), `1547041C` (2), `1572177N` (2), … +2 more |
| AL MAJD | matricule_fiscal | 7 | 27% | merge | `1255833F` (4), `853401G` (3), `1224618E` (2), `1587776J` (2), `428748M` (2), … +2 more |
| ALMAS | matricule_fiscal | 7 | 33% | merge | `755592H` (12), `644590P` (8), `1576701D` (5), `1323279H` (4), `1327943K` (3), … +2 more |
| BB | registre_commerce | 7 | 43% | merge | `B0126342006` (6), `B2413162006` (3), `0029872018` (1), `B01192322016` (1), `B02124052015` (1), … +2 more |
| CIE TUNISIENNE DES SACS CTS | registre_commerce | 7 | 46% | merge | `B19711998` (10), `B133171996` (8), `B24142122009` (5), `D19711998` (2), `B0132942008` (1), … +2 more |
| COBRA | matricule_fiscal | 7 | 36% | merge | `1007609S` (9), `1381615C` (5), `1260040M` (3), `914776B` (3), `1089150E` (2), … +2 more |
| COGEM + | matricule_fiscal | 7 | 60% | merge | `34378S` (21), `418487E` (7), `1353488G` (3), `1278879V` (1), `32593P` (1), … +2 more |
| DALIA | matricule_fiscal | 7 | 30% | merge | `1292725L` (3), `1203453L` (2), `1381117N` (1), `1417989B` (1), `539000N` (1), … +2 more |
| ECOLE PRIVEE EL-IMTIEZ | matricule_fiscal | 7 | 22% | merge | `515159J` (4), `864415Y` (4), `1412067E` (2), `1518775Z` (2), `1550854J` (2), … +2 more |
| ERRAHMA | registre_commerce | 7 | 85% | merge | `B0319512007` (67), `B2538722005` (7), `B0193162015` (2), `80319512007` (1), `B03195` (1), … +2 more |
| ETABLISSEMENT GHORBEL | registre_commerce | 7 | 25% | merge | `B086852008` (3), `130362001` (2), `B155891996` (2), `B189411999` (2), `B08242532012` (1), … +2 more |
| HAFEDH | matricule_fiscal | 7 | 50% | merge | `1187574Z` (11), `1186453L` (4), `1008727C` (2), `1590073H` (2), `10190311K` (1), … +2 more |
| HOTELIERE ET IMMOBILIERE AMILCAR | matricule_fiscal | 7 | 36% | merge | `5599S` (5), `1183416S` (2), `1302718V` (2), `1375994Q` (2), `1120798B` (1), … +2 more |
| JUNIOR | registre_commerce | 7 | 28% | merge | `B0174932007` (7), `B0757932005` (6), `B2550202006` (4), `B0183352013` (3), `B036602009` (3), … +2 more |
| L'OLIVIER BLEU DE RESTAURATION ET DE LOISIRS | registre_commerce | 7 | 41% | merge | `B2447342011` (7), `B01229412012` (2), `B07143242011` (2), `B14052003` (2), `B25149432011` (2), … +2 more |
| LA GENERALE DE DISTRIBUTION | matricule_fiscal | 7 | 31% | merge | `972084C` (4), `1250085W` (3), `895053M` (3), `1110385C` (2), `1320787L` (2), … +2 more |
| LA PERLE | matricule_fiscal | 7 | 20% | merge | `1496264H` (3), `1195104S` (2), `1298868C` (2), `1421776T` (2), `1535932R` (2), … +2 more |
| LA ROSA | registre_commerce | 7 | 33% | merge | `B157982002` (4), `B01187332016` (2), `B2724692004` (2), `B0230572013` (1), `B07259082016` (1), … +2 more |
| LA SIRENE | matricule_fiscal | 7 | 26% | merge | `1366894L` (5), `997987S` (5), `1119848C` (3), `624486E` (3), `1094410P` (1), … +2 more |
| LE MOTEUR | registre_commerce | 7 | 30% | merge | `B15227622016` (6), `B1541998` (4), `B0812102010` (3), `B8120372013` (3), `B8120252013` (2), … +2 more |
| LE PROGRES | matricule_fiscal | 7 | 42% | merge | `614801P` (10), `1087443G` (4), `1269316L` (3), `1501956R` (2), `1508718J` (2), … +2 more |
| ME CONSULTANTS | registre_commerce | 7 | 57% | merge | `B0323562004` (17), `B08100642013` (5), `B125042003` (3), `B12732001` (2), `B0123492004` (1), … +2 more |
| METALCO | matricule_fiscal | 7 | 22% | merge | `1257855W` (4), `46793T` (4), `623899T` (4), `635539K` (2), `924057F` (2), … +2 more |
| OXYGEN INTERNATIONAL | registre_commerce | 7 | 25% | merge | `B2492172007` (3), `B1456352005` (2), `B172791999` (2), `B249172007` (2), `B1127271997` (1), … +2 more |
| PREMIUM | registre_commerce | 7 | 25% | merge | `133202001` (4), `B24199182010` (4), `B01173652012` (2), `B04212132015` (2), `B2682612014` (2), … +2 more |
| PYRAMIDE PRESTIGE | matricule_fiscal | 7 | 20% | merge | `1156199A` (2), `1326996V` (2), `1554391Q` (2), `1042581Y` (1), `1218321B` (1), … +2 more |
| R M ELEGANCE | matricule_fiscal | 7 | 17% | merge | `1124391Y` (2), `1280979T` (2), `1422288L` (2), `1501241L` (2), `1542277A` (2), … +2 more |
| SATEX | matricule_fiscal | 7 | 27% | merge | `1002394A` (3), `1566925N` (2), `1590166M` (2), `1533210J` (1), `635890N` (1), … +2 more |
| SIAM | matricule_fiscal | 7 | 21% | merge | `1290393C` (3), `982529R` (3), `1419678X` (2), `1443611R` (2), `968167A` (2), … +2 more |
| SMC | matricule_fiscal | 7 | 17% | merge | `1382565P` (2), `141769K` (2), `1512084B` (2), `1575399P` (2), `835909E` (2), … +2 more |
| SOCIETE ANONYME IMMOBILIERE DU NORD DE LA TUNISIE | registre_commerce | 7 | 70% | merge | `B1134041997` (26), `B119041998` (3), `B0152672004` (2), `B187921996` (2), `B6151996` (2), … +2 more |
| SOCIETE DE REPARATION ET DE MAINTENANCE SRM | matricule_fiscal | 7 | 23% | merge | `1353674G` (3), `1209446N` (2), `1412122H` (2), `1474605P` (2), `452540M` (2), … +2 more |
| SOCIETE DINA | matricule_fiscal | 7 | 23% | merge | `1253454P` (3), `1384029C` (3), `1328329X` (2), `1519701J` (2), `1534300J` (1), … +2 more |
| SOCIETE EL-ANDALOUS | registre_commerce | 7 | 39% | merge | `B023142013` (7), `B1513311998` (4), `B144061999` (3), `231412013` (1), `B0231412012` (1), … +2 more |
| SOCIETE EL-BADR | matricule_fiscal | 7 | 45% | merge | `900571R` (9), `1105185M` (2), `13868905A` (2), `1425475A` (2), `1564623S` (2), … +2 more |
| SOCIETE ETABLISSEMENT TRIKI | registre_commerce | 7 | 31% | merge | `B19311997` (4), `B0386292014` (2), `B1100761996` (2), `B4014222010` (2), `A14179932013` (1), … +2 more |
| SOCIETE GENERALE MAKNI DE COMMERCE GMC | matricule_fiscal | 7 | 59% | merge | `900647V` (13), `1328471C` (2), `1331285C` (2), `1341295K` (2), `1078330X` (1), … +2 more |
| SOCIETE HAMZA | registre_commerce | 7 | 31% | merge | `B152682002` (4), `B25117372012` (3), `B25120702011` (2), `A1491472008` (1), `A23236072017` (1), … +2 more |
| SOCIETE IDEAL CONFECTION | matricule_fiscal | 7 | 26% | merge | `459621S` (5), `1296797W` (4), `1031120L` (3), `1313127L` (3), `1513157F` (2), … +2 more |
| SOCIETE INSIDE | matricule_fiscal | 7 | 37% | merge | `1191348V` (7), `993758N` (3), `1221610H` (2), `1458775P` (2), `1595441J` (2), … +2 more |
| SOCIETE INTERNATIONAL TRADING COMPANY | matricule_fiscal | 7 | 33% | merge | `1432918Z` (11), `1238613X` (7), `1189076T` (4), `31475E` (4), `1135447G` (3), … +2 more |
| SOCIETE INTERPROFESSIONNELLE POUR LA COMPENSATION ET LE DEPOT DES VALEURS MOBILIERES STICODEVAM | registre_commerce | 7 | 48% | merge | `B163781996` (21), `B16378` (14), `B112092001` (4), `B114761996` (2), `B0187252017` (1), … +2 more |
| SOCIETE LE LIVRE | matricule_fiscal | 7 | 27% | merge | `975957R` (3), `1485198F` (2), `1597213G` (2), `1138832A` (1), `1159176E` (1), … +2 more |
| SOCIETE MULTISERVICES | registre_commerce | 7 | 20% | merge | `B0159532006` (2), `B0178222008` (2), `B1128441997` (2), `B0863152006` (1), `B20159902010` (1), … +2 more |
| SOCIETE NARJES | matricule_fiscal | 7 | 26% | merge | `487745M` (5), `505776Z` (4), `610315M` (3), `1037835S` (2), `25114S` (2), … +2 more |
| SOCIETE NEJMA CONFECTION | matricule_fiscal | 7 | 22% | merge | `1483879R` (4), `718567Y` (4), `1051248N` (3), `14833879R` (3), `1490213V` (2), … +2 more |
| SOCIETE NERMINE | matricule_fiscal | 7 | 17% | merge | `1276633P` (2), `1291549J` (2), `1482986P` (2), `1596251J` (2), `1599959D` (2), … +2 more |
| SOCIETE NOUVELLE DE BRASSERIE | matricule_fiscal | 7 | 36% | merge | `940993H` (26), `644969F` (21), `17216B` (13), `856056Y` (10), `17216R` (2), … +2 more |
| SOCIETE NOUVELLE DE BRASSERIE | registre_commerce | 7 | 31% | merge | `B0120492006` (19), `B182181999` (18), `B153482003` (10), `B145281999` (6), `B154281999` (6), … +2 more |
| SOCIETE TOURISTIQUE EL-MOURADI | registre_commerce | 7 | 31% | merge | `B2591996` (34), `B0936852004` (31), `B0945782008` (21), `B154762003` (12), `B110596199` (8), … +2 more |
| SOCIETE TUNISIAN MINING SERVICES TMS | matricule_fiscal | 7 | 32% | merge | `885534V` (9), `1031655P` (8), `1117724G` (3), `1090453J` (2), `1385234K` (2), … +2 more |
| SOCIETE VITAL | registre_commerce | 7 | 33% | merge | `B13632003` (9), `B179052000` (7), `B138672002` (4), `B0280002008` (3), `B0757282006` (2), … +2 more |
| SOCIETE ¨PALM | registre_commerce | 7 | 28% | merge | `B0963032008` (5), `B169581996` (4), `B1989952008` (3), `B157111996` (2), `B1914712009` (2), … +2 more |
| STEG ENERGIES RENOUVELABLES STEG ER | matricule_fiscal | 7 | 31% | merge | `996151Z` (4), `1231993T` (2), `1295958Q` (2), `984825F` (2), `1152542C` (1), … +2 more |
| STPH | matricule_fiscal | 7 | 37% | merge | `620545F` (13), `1333416D` (6), `1334455Q` (6), `1113345G` (4), `620861Q` (3), … +2 more |
| STPH | registre_commerce | 7 | 47% | merge | `B1682001` (8), `B160351999` (3), `101636272009` (2), `1631411998` (1), `B061136272009` (1), … +2 more |
| STUDI | matricule_fiscal | 7 | 36% | merge | `1031438G` (11), `1227137E` (7), `1328566J` (6), `1023394Q` (3), `1549501T` (2), … +2 more |
| TUNISIE TRAVAUX | registre_commerce | 7 | 27% | merge | `B136082000` (4), `B0910232005` (3), `B131362003` (3), `B02234742016` (2), `B0151532007` (1), … +2 more |
| ACCESSOIRES TEXTILES COMPANY ATC | matricule_fiscal | 6 | 55% | merge | `836930F` (11), `1282365B` (2), `1376096S` (2), `1551001Y` (2), `1598646J` (2), … +1 more |
| AGENCE METROPOLITAINE DE COMMUNICATION AMC | matricule_fiscal | 6 | 27% | merge | `1121499X` (3), `11338901P` (2), `1426882R` (2), `1565735E` (2), `1125531W` (1), … +1 more |
| AGHIR | matricule_fiscal | 6 | 27% | merge | `10315Y` (3), `1034536W` (2), `118470L` (2), `24758W` (2), `1184760L` (1), … +1 more |
| AGRIMED | matricule_fiscal | 6 | 62% | merge | `583952G` (15), `839253D` (3), `1496292M` (2), `1558373F` (2), `1455672V` (1), … +1 more |
| AMC ERNST ET YOUNG | registre_commerce | 6 | 48% | merge | `B178441996` (20), `B170281997` (15), `B2447072008` (3), `B170701998` (2), `B170281991` (1), … +1 more |
| ARAMYS | registre_commerce | 6 | 40% | merge | `B248922006` (8), `B110098199` (6), `B117732002` (3), `110098199` (1), `B05117292010` (1), … +1 more |
| AZIZA | registre_commerce | 6 | 44% | merge | `B09181872009` (7), `B31144042012` (3), `B0897792018` (2), `B1103281997` (2), `B2427952007` (1), … +1 more |
| CERAMICA | matricule_fiscal | 6 | 36% | merge | `1393309J` (8), `857792E` (5), `1515571A` (4), `1200381Z` (3), `1296278B` (1), … +1 more |
| CHIC | registre_commerce | 6 | 33% | merge | `B0150892004` (5), `B0147982008` (3), `B034022009` (2), `B0722442005` (2), `B162611996` (2), … +1 more |
| CLEOPATRE | matricule_fiscal | 6 | 62% | merge | `965474W` (15), `1105965J` (2), `1135518E` (2), `1293602E` (2), `1459098D` (2), … +1 more |
| COGEM + | registre_commerce | 6 | 76% | merge | `B157671997` (27), `B157651997` (4), `B811522013` (4), `B167651997` (3), `B02118972014` (2), … +1 more |
| DISTRIBUTION INFINITY PRODUCTS DIP | matricule_fiscal | 6 | 31% | merge | `1415621L` (5), `1388277K` (3), `1567012H` (3), `1450548V` (2), `1550101X` (2), … +1 more |
| EL ALIA | registre_commerce | 6 | 31% | merge | `B04216532011` (5), `B04148192013` (3), `B137892001` (3), `B04162562014` (2), `B04167522016` (2), … +1 more |
| ETABLISSEMENT ABDELMOULA | registre_commerce | 6 | 44% | merge | `B114121` (4), `B0158391996` (1), `B1110701997` (1), `B1141211997` (1), `B158391996` (1), … +1 more |
| FLOWER | matricule_fiscal | 6 | 62% | merge | `5924K` (9), `1139107F` (2), `1520333W` (2), `1329330T` (1), `1402054H` (1), … +1 more |
| GENERALE CONFECTION | matricule_fiscal | 6 | 33% | merge | `1277324P` (2), `1277624P` (2), `1343530K` (2), `1566746M` (2), `635708J` (2), … +1 more |
| HENKEL ALKI | registre_commerce | 6 | 26% | merge | `B0115402009` (11), `B17691996` (8), `17691996` (7), `B0132772009` (7), `B138881996` (7), … +1 more |
| HOPE | matricule_fiscal | 6 | 20% | merge | `1307384P` (2), `1477262Z` (2), `1510085T` (2), `1535596W` (2), `1445290D` (1), … +1 more |
| ILEF | matricule_fiscal | 6 | 23% | merge | `1193680N` (3), `492443J` (3), `1465231C` (2), `1569028X` (2), `902977V` (2), … +1 more |
| INGENIUM SA | matricule_fiscal | 6 | 40% | merge | `1351396V` (8), `1228097T` (4), `1349785J` (2), `1465661X` (2), `1472648S` (2), … +1 more |
| INTERNATIONAL TELE CONSULTANTS | matricule_fiscal | 6 | 40% | merge | `1184858W` (8), `1482995Q` (5), `1009813D` (3), `1025880S` (2), `1546221A` (1), … +1 more |
| KENZA CONFECTION | matricule_fiscal | 6 | 20% | merge | `1163803P` (2), `1184411R` (2), `1310891E` (2), `31101A` (2), `1024565W` (1), … +1 more |
| LA MEDITERRANEENNE | matricule_fiscal | 6 | 31% | merge | `1043200Z` (4), `1292534F` (3), `1131153C` (2), `1334886L` (2), `1139189A` (1), … +1 more |
| LA PRINCESSE | matricule_fiscal | 6 | 33% | merge | `1343871E` (7), `1431975E` (5), `1185113N` (3), `1276030R` (2), `1417656G` (2), … +1 more |
| LA SOURCE | registre_commerce | 6 | 30% | merge | `B24124862009` (6), `B0269052008` (5), `B15103912010` (3), `B01203712012` (2), `B016502013` (2), … +1 more |
| LE PILOTE | registre_commerce | 6 | 36% | merge | `B148161996` (5), `0840482006` (2), `B013562007` (2), `B1107051996` (2), `B2279322011` (2), … +1 more |
| LE PROFILE ALUMINIUM | registre_commerce | 6 | 42% | merge | `B2414532005` (14), `B1060332016` (9), `B1112491996` (8), `B1414531005` (3), `B15159552015` (1), … +1 more |
| MAGASIN GENERAL | matricule_fiscal | 6 | 49% | merge | `32792V` (17), `1597667K` (6), `33128W` (6), `1522968L` (2), `1578030V` (2), … +1 more |
| MAGHREB INTERNATIONAL PUBLICITE MIP | matricule_fiscal | 6 | 47% | merge | `867795N` (22), `826555X` (17), `1085799A` (4), `1393140B` (2), `1044729J` (1), … +1 more |
| MANAGER | matricule_fiscal | 6 | 35% | merge | `549184N` (6), `1573253M` (3), `791031G` (3), `1380839N` (2), `1506596J` (2), … +1 more |
| MARHABA | registre_commerce | 6 | 71% | merge | `B110832199` (25), `B110832` (3), `B1531998` (3), `B119911997` (2), `B096322008` (1), … +1 more |
| NESRINE | registre_commerce | 6 | 25% | merge | `B0646752004` (2), `B126062000` (2), `B03149412014` (1), `B0719722006` (1), `B127932002` (1), … +1 more |
| NOURTEX CONFECTION | matricule_fiscal | 6 | 33% | merge | `580168B` (5), `1248880W` (4), `1326235H` (2), `1439806X` (2), `1032117W` (1), … +1 more |
| PANORAMA | registre_commerce | 6 | 56% | merge | `B17741996` (13), `B110311199` (5), `B1125262017` (2), `B112482000` (1), `B154402001` (1), … +1 more |
| POLYMONT INGENIERIE CONSULTING | registre_commerce | 6 | 22% | merge | `B01148362017` (2), `B2456162007` (2), `B405452018` (2), `B02185952016` (1), `B027882013` (1), … +1 more |
| PROLOGIC HOLDING | matricule_fiscal | 6 | 38% | merge | `544435X` (29), `1219330G` (19), `644572M` (14), `1219836G` (5), `1389601F` (5), … +1 more |
| SARA DE CONFECTION | matricule_fiscal | 6 | 23% | merge | `450401S` (3), `1042585C` (2), `1273536B` (2), `1277959P` (2), `1507292Z` (2), … +1 more |
| SILVER SAPHIR | registre_commerce | 6 | 32% | merge | `B12832000` (7), `B071652009` (6), `B1283200` (3), `B24189372009` (3), `1257855` (2), … +1 more |
| SOCIETE AMIR DE COMMERCE | matricule_fiscal | 6 | 25% | merge | `1468828Q` (3), `1534952R` (3), `1526823L` (2), `1547201A` (2), `1425019D` (1), … +1 more |
| SOCIETE ANIS | registre_commerce | 6 | 20% | merge | `B0967172007` (2), `B24227262010` (2), `B3175472009` (2), `B51231832016` (2), `A20225812016` (1), … +1 more |
| SOCIETE ANONYME IMMOBILIERE DU NORD DE LA TUNISIE | matricule_fiscal | 6 | 59% | merge | `6175A` (10), `510814W` (2), `539731T` (2), `4959441P` (1), `496236W` (1), … +1 more |
| SOCIETE BS DIAGNOSTICS | matricule_fiscal | 6 | 35% | merge | `1554065D` (7), `1203042V` (4), `642728F` (4), `1121428F` (2), `1512196J` (2), … +1 more |
| SOCIETE CARTE | matricule_fiscal | 6 | 47% | merge | `927109N` (9), `1246349X` (4), `1383617N` (2), `205M` (2), `1180567V` (1), … +1 more |
| SOCIETE CHAARI FRERES SCF | matricule_fiscal | 6 | 36% | merge | `1358093M` (5), `995441C` (4), `634900C` (2), `503092S` (1), `537309Z` (1), … +1 more |
| SOCIETE CHAARI FRERES SCF | registre_commerce | 6 | 25% | merge | `B0818052007` (2), `B16902001` (2), `8084432006` (1), `B1107481997` (1), `B1121491997` (1), … +1 more |
| SOCIETE DE SERVICES ADMINISTRATIFS | matricule_fiscal | 6 | 29% | merge | `1542237R` (5), `1263617W` (3), `1287162N` (3), `1476641C` (2), `1500529W` (2), … +1 more |
| SOCIETE EL-BADR | registre_commerce | 6 | 47% | merge | `B081072005` (9), `B0853472008` (3), `80728562015` (2), `B16691999` (2), `B2599272009` (2), … +1 more |
| SOCIETE EL-MAJD | registre_commerce | 6 | 22% | merge | `B1114241997` (2), `B151422003` (2), `B2210022007` (2), `A2218312009` (1), `B2287302010` (1), … +1 more |
| SOCIETE ELEMENTS + | matricule_fiscal | 6 | 33% | merge | `1307434G` (4), `1573509S` (2), `1586756A` (2), `496781S` (2), `419049P` (1), … +1 more |
| SOCIETE FAIZA | matricule_fiscal | 6 | 29% | merge | `4054H` (4), `381507R` (2), `454938Q` (2), `908422N` (2), `916404H` (2), … +1 more |
| SOCIETE FAIZA | registre_commerce | 6 | 25% | merge | `081159397` (3), `B0110652005` (3), `B159461997` (2), `B2427762006` (2), `B1113311998` (1), … +1 more |
| SOCIETE HAIFA | registre_commerce | 6 | 36% | merge | `B134542002` (13), `B2414932004` (8), `B198252010` (6), `B2453392005` (6), `B2489432008` (2), … +1 more |
| SOCIETE IDEAL SERVICE | matricule_fiscal | 6 | 32% | merge | `382095X` (6), `1538563Z` (4), `1020508T` (3), `1077576P` (2), `1361343L` (2), … +1 more |
| SOCIETE INOV | matricule_fiscal | 6 | 36% | merge | `1260904M` (4), `1596777L` (2), `858940C` (2), `1044134L` (1), `565640Q` (1), … +1 more |
| SOCIETE INTERACTIVE | registre_commerce | 6 | 32% | merge | `B0314032005` (6), `B012292007` (4), `0122912214` (3), `B1108451997` (2), `B139312003` (2), … +1 more |
| SOCIETE MAGHREBINE DES PRODUITS CERAMIQUES SMPC | registre_commerce | 6 | 55% | merge | `B620919971` (12), `B16209` (3), `B162091997` (3), `60744612007` (2), `024021` (1), … +1 more |
| SOCIETE MEDITERRANEENNE DE CONSERVE SOMECO | matricule_fiscal | 6 | 25% | merge | `418537X` (3), `761724P` (3), `34215Y` (2), `34280Y` (2), `418817C` (1), … +1 more |
| SOCIETE NARJES | registre_commerce | 6 | 38% | merge | `B157181998` (2), `B158362002` (2), `B16088` (1), `B160881996` (1), `D1583998` (1), … +1 more |
| SOCIETE SAHA | matricule_fiscal | 6 | 27% | merge | `1263991R` (4), `1543653J` (3), `1031968F` (2), `1288850L` (2), `1319810A` (2), … +1 more |
| SOCIETE SIRINE | registre_commerce | 6 | 41% | merge | `B147491997` (12), `B2577952011` (6), `B133592003` (5), `B0834992009` (4), `B08197052013` (1), … +1 more |
| SOCIETE SOUAD | matricule_fiscal | 6 | 20% | merge | `1491816X` (3), `505682T` (3), `859416Q` (3), `1564749G` (2), `1569233D` (2), … +1 more |
| SOCIETE TOURISTIQUE | registre_commerce | 6 | 60% | merge | `B110781199` (12), `B150761997` (3), `B116262001` (2), `B0116062016` (1), `B10781199` (1), … +1 more |
| SOCIETE TUNISIENNE DE SERVICES | matricule_fiscal | 6 | 52% | merge | `886782P` (11), `1336481B` (3), `1129804V` (2), `1219184Q` (2), `1259241D` (2), … +1 more |
| SOGES | matricule_fiscal | 6 | 50% | merge | `434386T` (8), `846879B` (3), `1597899A` (2), `1247170R` (1), `1370171K` (1), … +1 more |
| SOGES | registre_commerce | 6 | 55% | merge | `B150112001` (11), `B125032001` (3), `B139622003` (3), `B158200` (1), `B1582001` (1), … +1 more |
| SPECTRA PEINTURE | matricule_fiscal | 6 | 46% | merge | `584191S` (11), `1023513D` (5), `1341721G` (4), `1085754L` (2), `1023518D` (1), … +1 more |
| STPA | matricule_fiscal | 6 | 29% | merge | `1021569M` (4), `1097835A` (3), `1001804S` (2), `1079536P` (2), `1545315B` (2), … +1 more |
| TAIBA | matricule_fiscal | 6 | 33% | merge | `1150389D` (4), `1404909Q` (3), `1485156V` (2), `1186194L` (1), `1258183G` (1), … +1 more |
| TAYSIR | registre_commerce | 6 | 33% | merge | `B08106662014` (4), `B2799632011` (3), `B0171842013` (2), `B08265402018` (1), `B0885292008` (1), … +1 more |
| TELECONTROL DETECTION SYSTEM TDS | matricule_fiscal | 6 | 52% | merge | `1054860R` (12), `635747R` (5), `1248870T` (2), `1485084W` (2), `1413792X` (1), … +1 more |
| TRACE | matricule_fiscal | 6 | 27% | merge | `1175380B` (3), `1335287X` (2), `1489996X` (2), `1551467F` (2), `1198992Z` (1), … +1 more |
| VICTOIRE POUR LA FEMME RURALE | matricule_fiscal | 6 | 30% | merge | `349466R` (3), `1298800F` (2), `1486945X` (2), `829456H` (1), `838167C` (1), … +1 more |
| WELCOME | matricule_fiscal | 6 | 36% | merge | `1002147L` (8), `941374P` (5), `1277222C` (3), `995751P` (3), `1375601H` (2), … +1 more |
| ZINA DES TRAVAUX PUBLICS | matricule_fiscal | 6 | 42% | merge | `349837W` (11), `925722W` (6), `1400378S` (3), `927957Y` (3), `1334673Z` (2), … +1 more |
| ZINA DES TRAVAUX PUBLICS | registre_commerce | 6 | 33% | merge | `B081762004` (6), `B2435002005` (6), `B0343352005` (3), `B0166782006` (1), `B115352001` (1), … +1 more |
| ACADEMIE PYTHAGORE AP | matricule_fiscal | 5 | 57% | merge | `1452156Q` (7), `1278300D` (2), `1294538T` (2), `1582969V` (2), `1452166Q` (1) |
| ALMAS | registre_commerce | 5 | 59% | merge | `B083172004` (17), `B01155542018` (4), `B01210702013` (4), `B03236942013` (3), `B09127742018` (1) |
| AMAL DE COMMERCE | matricule_fiscal | 5 | 20% | merge | `1155339P` (2), `1282405R` (2), `1304910B` (2), `1429085G` (2), `923836S` (2) |
| ASTERIA | matricule_fiscal | 5 | 29% | merge | `1214241K` (4), `1324224W` (4), `1485976A` (2), `1499044K` (2), `961393D` (2) |
| ASTUCE FORMATION | matricule_fiscal | 5 | 25% | merge | `1328505V` (2), `1461316P` (2), `980795A` (2), `1135256B` (1), `1463012J` (1) |
| AYA DISTRIBUTION | matricule_fiscal | 5 | 25% | merge | `1405037V` (2), `1532442P` (2), `1554539S` (2), `1017841E` (1), `1115441P` (1) |
| BATIMENT + | registre_commerce | 5 | 40% | merge | `B01179942014` (4), `B115791997` (2), `B40131962012` (2), `B1684332015` (1), `B246342004` (1) |
| BATIMENT ET TRAVAUX PUBLICS | matricule_fiscal | 5 | 45% | merge | `1414945A` (9), `1127460G` (4), `1593369K` (3), `433032P` (3), `612263B` (1) |
| BATINOX | matricule_fiscal | 5 | 79% | merge | `863030E` (19), `761543L` (2), `1207417Z` (1), `312335R` (1), `941536P` (1) |
| CIE TUNISIENNE DES SACS CTS | matricule_fiscal | 5 | 33% | merge | `1116277A` (5), `614715S` (5), `1048950E` (3), `1165104B` (1), `943434S` (1) |
| COBRA | registre_commerce | 5 | 30% | merge | `B086482015` (3), `B24149162012` (3), `B1113501996` (2), `B01221762012` (1), `B2447292005` (1) |
| COMPETENCES+ | registre_commerce | 5 | 40% | merge | `B2467052006` (4), `B2514712010` (3), `B01154632013` (1), `B02213552011` (1), `B02214472011` (1) |
| COOPER TUNISIE ICT | registre_commerce | 5 | 35% | merge | `B0130552006` (6), `D014852004` (5), `0014852004` (4), `B2417832011` (1), `D015452006` (1) |
| DAR ESSAIDALI | matricule_fiscal | 5 | 51% | merge | `18425N` (36), `45365X` (17), `1060553W` (10), `18470T` (5), `18411N` (2) |
| DISCOVERY INFORMATIQUE | registre_commerce | 5 | 40% | merge | `A153992003` (17), `B017832005` (14), `B01783` (9), `3017832005` (1), `B116931996` (1) |
| DOLCE VITA DE PROMOTION IMMOBILIERE | matricule_fiscal | 5 | 33% | merge | `1176253Z` (4), `1088524L` (3), `1412915K` (2), `601697Q` (2), `878163V` (1) |
| ENNAJEH | matricule_fiscal | 5 | 33% | merge | `918476J` (4), `1146381Q` (3), `1198243R` (2), `1536547Q` (2), `840327W` (1) |
| ENNASR | registre_commerce | 5 | 56% | merge | `B111576199` (5), `B0328592008` (1), `B0939842011` (1), `B129001997` (1), `B4011192015` (1) |
| ENTREPRISE EL-AMEN | registre_commerce | 5 | 59% | merge | `B13195922010` (16), `B114132003` (5), `B0357942008` (4), `B153541999` (1), `B5162692017` (1) |
| ESSALEM | matricule_fiscal | 5 | 60% | merge | `1036121J` (26), `470858K` (8), `956062C` (6), `1357866F` (2), `772329R` (1) |
| ETABLISSEMENT ABDELMOULA | matricule_fiscal | 5 | 33% | merge | `11987P` (4), `1546849H` (2), `1569363N` (2), `18126E` (2), `368326H` (2) |
| EUROMED CONSULTING | matricule_fiscal | 5 | 39% | merge | `1043860G` (7), `1170497S` (4), `1032306Z` (3), `1177637R` (2), `1349432K` (2) |
| FARAH | registre_commerce | 5 | 52% | merge | `B134802003` (17), `B110671997` (11), `B07107082009` (3), `B072880201` (1), `B0728802012` (1) |
| FRESH FISH | matricule_fiscal | 5 | 42% | merge | `1223217L` (5), `1449839M` (2), `1563700J` (2), `1568073B` (2), `1272084P` (1) |
| GALLAND ETABLISSEMENT STABLE | registre_commerce | 5 | 50% | merge | `B0171712011` (4), `B01124452016` (1), `B0152132004` (1), `B136312003` (1), `B197021999` (1) |
| GENERALE TEXTILE | registre_commerce | 5 | 58% | merge | `A0114072008` (26), `B154451999` (11), `B140701997` (5), `B251942009` (2), `B0115392008` (1) |

_3806 further conflicts are in `org_identifiers.csv`, where `is_conflicting = 1`._
