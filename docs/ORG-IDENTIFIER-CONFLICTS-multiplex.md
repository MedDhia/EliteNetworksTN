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
| matricule_fiscal | 2318 of 78944 carrying one (3%) |
| registre_commerce | 2162 of 33558 carrying one (6%) |

Of 4480 conflicts over **3582 organisations**, **3342 read as merges** and 1138 as OCR damage. A conflict is one (organisation, identifier kind) pair, so a node with a bad matricule *and* a bad RC number counts twice here and once in that organisation total.

The distribution is not what a metadata problem looks like. The worst node, **SOCIETE M**, carries **154 distinct matricule fiscal values** over 373 observations, with its modal value accounting for only 3% of them. That is not one registration misread; it is a generic name fragment that every firm beginning with those words resolves onto.

**So the dominant failure in organisation resolution is the generic-name merge, not fuzzy-match noise.** A node like that does not degrade a variable — it fabricates a hub, and any centrality computed over it is meaningless. Treat the merge rows below as a blocklist: exclude those nodes, or split them, before using organisation-level structure.

Classifying these on the distance between the two closest values was the first attempt and it inverted the signal: among hundreds of numbers some pair is always one character apart, so the worst merges were labelled OCR. The test is instead whether the values cluster around the modal one.

## Conflicts, worst merges first

| organisation | identifier | values | modal share | reads as | most-observed values |
| --- | --- | --- | --- | --- | --- |
| SOCIETE M | matricule_fiscal | 154 | 3% | merge | `1387182Z` (10), `1293190F` (8), `992132D` (8), `1214095T` (7), `1283124P` (7), … +149 more |
| SOCIETE DE PROMOTION IMMOBILIERE | matricule_fiscal | 119 | 6% | merge | `754848J` (33), `570983W` (21), `719356S` (20), `833596Z` (13), `958310H` (13), … +114 more |
| SOCIETE DE PROMOTION IMMOBILIERE | registre_commerce | 113 | 4% | merge | `B110002001` (21), `B151252000` (18), `B130991997` (17), `B2425942007` (14), `B1117961997` (12), … +108 more |
| SMAG | matricule_fiscal | 73 | 7% | merge | `953145R` (10), `1143469K` (5), `1298734N` (4), `1211768A` (3), `1242010D` (3), … +68 more |
| BB | matricule_fiscal | 62 | 5% | merge | `958835J` (6), `975694M` (6), `1161062R` (5), `1472588Y` (5), `1173553W` (3), … +57 more |
| SPEED | matricule_fiscal | 50 | 7% | merge | `1489982Q` (8), `809748G` (6), `1135020G` (4), `1068883X` (3), `1147532R` (3), … +45 more |
| SOCIETE EL-BARAKA | matricule_fiscal | 47 | 9% | merge | `349694Z` (8), `943515F` (5), `952921E` (5), `1279563F` (4), `1320541P` (4), … +42 more |
| LES GRANDS MOULINS DU SUD GMS | matricule_fiscal | 46 | 6% | merge | `335062Y` (4), `635563K` (4), `1234604D` (3), `271Y` (3), `658P` (3), … +41 more |
| LINK | matricule_fiscal | 45 | 20% | merge | `1001375S` (32), `1214663E` (15), `904223Q` (12), `1226388T` (9), `1029460J` (5), … +40 more |
| SOCIETE EVENT | matricule_fiscal | 45 | 12% | merge | `816663R` (15), `795140D` (10), `1477001D` (6), `1481965E` (5), `1113398W` (4), … +40 more |
| SOCIETE BAYA | matricule_fiscal | 43 | 6% | merge | `1152411R` (6), `1152664M` (5), `1270226B` (5), `1281396E` (3), `1366721P` (3), … +38 more |
| SOCIETE UNIQUE | matricule_fiscal | 43 | 22% | merge | `947693D` (28), `2309D` (11), `431699A` (7), `1348069G` (5), `965502G` (4), … +38 more |
| SOCIETE ADEM | matricule_fiscal | 42 | 6% | merge | `1314988F` (5), `1240148N` (4), `1280773F` (4), `889656X` (4), `1319477H` (3), … +37 more |
| LE FUTURE | matricule_fiscal | 39 | 18% | merge | `1021337X` (22), `960004W` (10), `1323377J` (7), `1261503C` (5), `1361978S` (5), … +34 more |
| LE MOTEUR | matricule_fiscal | 39 | 12% | merge | `1283400Q` (14), `1130552K` (10), `1483726Z` (8), `836992W` (8), `1283427C` (6), … +34 more |
| SAAD | matricule_fiscal | 38 | 7% | merge | `958779T` (6), `1145981F` (5), `779285C` (5), `1192202F` (4), `1195307C` (4), … +33 more |
| SOCIETE DASSISTANCE ET GESTION ITALO TUNISIENNE AGIT | matricule_fiscal | 38 | 5% | merge | `1323240R` (4), `1177193J` (3), `1213047F` (3), `1220136Y` (3), `1468524B` (3), … +33 more |
| SOCIETE MULTISERVICES | matricule_fiscal | 38 | 11% | merge | `760474L` (9), `1028994G` (4), `1597194X` (4), `1604206C` (4), `1425684H` (3), … +33 more |
| CARTHAGO SA | matricule_fiscal | 36 | 20% | merge | `35760Z` (22), `1016555X` (12), `579940Y` (5), `644548M` (5), `875861C` (5), … +31 more |
| EMNA | matricule_fiscal | 36 | 11% | merge | `1104866C` (10), `983196V` (7), `1350906Q` (5), `418040A` (4), `520275W` (4), … +31 more |
| PREMIUM | matricule_fiscal | 36 | 8% | merge | `1249877F` (7), `510393W` (7), `1274758T` (5), `1028602A` (4), `1176662N` (4), … +31 more |
| SOCIETE INES | matricule_fiscal | 36 | 12% | merge | `433713J` (10), `913925R` (5), `1117976B` (3), `1207440Y` (3), `1226950Y` (3), … +31 more |
| SOCIETE JAWHARA | matricule_fiscal | 36 | 11% | merge | `496428C` (11), `918740F` (8), `738541Y` (7), `1238899C` (6), `1113076E` (5), … +31 more |
| SOCIETE VITAL | matricule_fiscal | 36 | 6% | merge | `1015913V` (5), `748728N` (5), `1629612W` (4), `712802N` (4), `822354X` (4), … +31 more |
| MODA | matricule_fiscal | 35 | 7% | merge | `1219980M` (6), `1177044W` (5), `1003502P` (4), `1203618P` (4), `1309829G` (4), … +30 more |
| SOCIETE IRIS | matricule_fiscal | 34 | 5% | merge | `1039951E` (3), `1059199G` (3), `1096655T` (3), `1315018Q` (3), `1377953P` (3), … +29 more |
| SOCIETE DE MISE EN VALEUR ET DE DEVELOPPEMENT AGRICOLE | matricule_fiscal | 33 | 8% | merge | `587620F` (13), `736406H` (13), `1361054E` (10), `349464L` (9), `1053615A` (8), … +28 more |
| SOCIETE DE MISE EN VALEUR ET DE DEVELOPPEMENT AGRICOLE | registre_commerce | 31 | 14% | merge | `B2469412008` (16), `B11291` (9), `B112912003` (9), `B131041997` (8), `B154371997` (7), … +26 more |
| AMANA | matricule_fiscal | 30 | 21% | merge | `1288542B` (18), `1437026R` (6), `504321Q` (5), `1208857A` (4), `10761959W` (3), … +25 more |
| STEP | matricule_fiscal | 30 | 15% | merge | `969271D` (13), `1251519F` (9), `1398104T` (5), `488136W` (4), `999308Q` (4), … +25 more |
| CENTRAL | matricule_fiscal | 29 | 18% | merge | `1287385C` (16), `986737Q` (9), `1184329Z` (5), `9247M` (5), `1218362L` (4), … +24 more |
| SOCIETE ZIED | matricule_fiscal | 29 | 12% | merge | `1411373X` (7), `1333716N` (4), `1090575T` (3), `1488292Q` (3), `1587249P` (3), … +24 more |
| SOCIETE ALFA | matricule_fiscal | 28 | 18% | merge | `623108A` (13), `901039E` (11), `1091356N` (3), `1107960M` (3), `1341333Y` (3), … +23 more |
| SOCIETE ENTREPRISE TRABELSI | matricule_fiscal | 28 | 17% | merge | `624954M` (11), `1294912W` (5), `584166R` (5), `1110303H` (3), `625305M` (3), … +23 more |
| SOCIETE GLOBE | matricule_fiscal | 28 | 9% | merge | `1044725E` (7), `1115642X` (6), `323694M` (6), `1263303E` (5), `774310N` (4), … +23 more |
| SOCIETE LE COIN | matricule_fiscal | 28 | 23% | merge | `1231067M` (18), `1125332Q` (5), `1223649H` (4), `1386252R` (4), `795077P` (4), … +23 more |
| SOCIETE YOSR | matricule_fiscal | 28 | 20% | merge | `587499Z` (13), `1050714P` (5), `1448814Y` (5), `1237692J` (4), `1363935P` (4), … +23 more |
| SOCIETE ANIS | matricule_fiscal | 27 | 13% | merge | `797092X` (8), `1485476J` (4), `1021546E` (3), `1189749N` (3), `1296386E` (3), … +22 more |
| SOCIETE ASMA | matricule_fiscal | 27 | 15% | merge | `1414847Z` (7), `778929M` (4), `1123535R` (2), `1190424K` (2), `1214105C` (2), … +22 more |
| SOCIETE NOUR | matricule_fiscal | 27 | 14% | merge | `620582L` (10), `1220246D` (7), `349539N` (7), `1301601C` (6), `1276669C` (4), … +22 more |
| SELECTION | matricule_fiscal | 26 | 11% | merge | `991762A` (7), `1014887G` (4), `1325703L` (4), `1343433K` (4), `430436T` (4), … +21 more |
| SOCIETE MABROUK | matricule_fiscal | 26 | 30% | merge | `580188F` (25), `1177809T` (6), `1165483C` (4), `385454N` (4), `966567E` (4), … +21 more |
| SOCIETE ¨PALM | matricule_fiscal | 26 | 10% | merge | `1065132Z` (7), `1028282E` (6), `1574595M` (5), `1146870D` (4), `1183545B` (4), … +21 more |
| LA ROSA | matricule_fiscal | 25 | 11% | merge | `1322794T` (6), `1524836H` (4), `1543744L` (4), `437882Q` (3), `1154Y` (2), … +20 more |
| LES HORIZONS | matricule_fiscal | 25 | 7% | merge | `1556071K` (4), `1122777E` (3), `1128494X` (3), `1286689M` (3), `1334844A` (3), … +20 more |
| MAYA | matricule_fiscal | 25 | 10% | merge | `1031522B` (6), `1212195N` (4), `1222536V` (4), `1327035F` (4), `1165010W` (3), … +20 more |
| PNEU | matricule_fiscal | 25 | 14% | merge | `1145573S` (10), `2172E` (9), `283866Q` (8), `1078824Q` (4), `1161611Z` (4), … +20 more |
| SOCIETE SALMA | matricule_fiscal | 25 | 20% | merge | `612787B` (12), `1059762M` (7), `1515306J` (4), `1403839P` (3), `1031764T` (2), … +20 more |
| LA PERLE | matricule_fiscal | 24 | 11% | merge | `1032351E` (6), `1208394P` (4), `1496264H` (3), `1503610A` (3), `747463C` (3), … +19 more |
| CHIC | matricule_fiscal | 23 | 10% | merge | `1056547T` (5), `897753T` (4), `1389757B` (3), `1398472R` (3), `1598457F` (3), … +18 more |
| EL FAOUZ | matricule_fiscal | 23 | 17% | merge | `1017737F` (11), `963770S` (8), `858402E` (6), `612789D` (4), `1089161H` (3), … +18 more |
| LES GRANDS MOULINS DU SUD GMS | registre_commerce | 23 | 35% | merge | `B131681997` (17), `B1118861996` (3), `B2430602012` (3), `B0255312005` (2), `B0635312008` (2), … +18 more |
| ME CONSULTANTS | matricule_fiscal | 23 | 23% | merge | `761845Y` (24), `980692T` (21), `1299448P` (7), `775137Y` (7), `1302629V` (5), … +18 more |
| PHENIX | matricule_fiscal | 23 | 14% | merge | `840725G` (9), `920386D` (7), `1261734R` (6), `510648A` (6), `1393399D` (4), … +18 more |
| SICAV ENTREPRISE | registre_commerce | 23 | 16% | merge | `B186251996` (20), `B11574` (17), `B115741997` (16), `B014377` (11), `B1157641997` (9), … +18 more |
| SOCIETE DE NUTRITION | matricule_fiscal | 23 | 25% | merge | `842437K` (21), `951570X` (9), `1113857C` (7), `737785N` (7), `2992K` (5), … +18 more |
| SOCIETE YASMINE | matricule_fiscal | 23 | 17% | merge | `588259N` (7), `1339595Z` (5), `1507929P` (3), `876898W` (3), `921899E` (3), … +18 more |
| GENERAL TRAVAUX DE CONSTRUCTION GTC | matricule_fiscal | 22 | 15% | merge | `1355310N` (7), `1458286B` (4), `1029981F` (2), `1037412X` (2), `1083764I` (2), … +17 more |
| CHAMS | matricule_fiscal | 21 | 12% | merge | `1158536F` (7), `19953N` (7), `199553N` (4), `9233F` (4), `1117131L` (3), … +16 more |
| EL HOUDA | matricule_fiscal | 21 | 18% | merge | `644485P` (11), `1013539J` (6), `1000837Y` (4), `1454781V` (4), `635896E` (4), … +16 more |
| EL WIFEK | matricule_fiscal | 21 | 11% | merge | `438610Z` (6), `784622H` (6), `1236696J` (4), `504352Y` (4), `510811S` (3), … +16 more |
| ENTREPRISE EL-AMEN | matricule_fiscal | 21 | 23% | merge | `718584Z` (18), `1176119T` (16), `1042279V` (12), `1063164Z` (6), `1108749Q` (4), … +16 more |
| SOCIETE EL-WIFAK | matricule_fiscal | 21 | 9% | merge | `433134V` (4), `283777Q` (3), `4414611N` (3), `74526033N` (3), `1092222D` (2), … +16 more |
| SOCIETE LE LABO | matricule_fiscal | 21 | 13% | merge | `1121630F` (7), `583889S` (7), `1100532P` (4), `766861V` (4), `1267726S` (3), … +16 more |
| SOCIETE REAL ESTATE | matricule_fiscal | 21 | 14% | merge | `1104105Q` (8), `1179884P` (6), `1010815X` (5), `1227214A` (5), `1119528N` (3), … +16 more |
| SOCIETE HAMZA | matricule_fiscal | 20 | 9% | merge | `1222016Z` (4), `1472494S` (4), `1253571T` (3), `1324193G` (3), `1580124W` (3), … +15 more |
| SOCIETE VITAL | registre_commerce | 20 | 13% | merge | `B13632003` (7), `B179052000` (7), `B0763542007` (5), `B138672002` (4), `B01229652013` (3), … +15 more |
| SOMAFRIP | matricule_fiscal | 20 | 22% | merge | `1386476G` (9), `1084894T` (2), `1086513Z` (2), `1223640Y` (2), `12526715S` (2), … +15 more |
| ARC EN CIEL | matricule_fiscal | 19 | 18% | merge | `1244934A` (11), `1357169L` (7), `775642L` (7), `1112658S` (5), `1065233D` (4), … +14 more |
| AZIZA | matricule_fiscal | 19 | 19% | merge | `968444G` (8), `1117381D` (3), `1265313Q` (3), `1488982L` (3), `1125265X` (2), … +14 more |
| ERRAHMA | matricule_fiscal | 19 | 64% | merge | `884195R` (68), `635620B` (10), `1025491Z` (3), `1029874D` (3), `1109154X` (2), … +14 more |
| GLOBAL SERVICES | matricule_fiscal | 19 | 29% | merge | `926133J` (14), `1003086V` (6), `1325021Q` (3), `1392746Y` (3), `1202376L` (2), … +14 more |
| NESRINE | matricule_fiscal | 19 | 9% | merge | `1360328H` (3), `1526961W` (3), `1217391M` (2), `1266529K` (2), `1330114D` (2), … +14 more |
| JUNIOR | matricule_fiscal | 18 | 20% | merge | `937275H` (11), `1025883M` (6), `975311G` (6), `1080559N` (3), `1295925F` (3), … +13 more |
| LINK | registre_commerce | 18 | 23% | merge | `B025042005` (12), `B25159372011` (12), `B2427862007` (9), `B2532822012` (3), `B1147652014` (2), … +13 more |
| PANORAMA | matricule_fiscal | 18 | 12% | merge | `296329M` (4), `905539N` (4), `1158603Z` (2), `1337403Q` (2), `1452580D` (2), … +13 more |
| SOCIETE AMEUR | registre_commerce | 18 | 24% | merge | `B170131997` (14), `B247502008` (14), `B0251892004` (7), `B115371996` (3), `B25178872011` (3), … +13 more |
| SOCIETE GENERALE DE MENUISERIE SOGEM | matricule_fiscal | 18 | 17% | merge | `789331W` (9), `968189G` (9), `420354M` (7), `1353970M` (3), `36847K` (3), … +13 more |
| TELNET ELECTRONICS | matricule_fiscal | 18 | 16% | merge | `1105484W` (6), `1180325C` (2), `1323741J` (2), `1388191E` (2), `1431847X` (2), … +13 more |
| CARTHAGO SA | registre_commerce | 17 | 15% | merge | `B2422622004` (7), `B2455392007` (7), `B157572002` (5), `B2432842004` (5), `B14462003` (3), … +12 more |
| ETABLISSEMENT GHORBEL | matricule_fiscal | 17 | 10% | merge | `1068472F` (3), `1035641A` (2), `1400355K` (2), `1410851C` (2), `1438797K` (2), … +12 more |
| LA FONDATION | matricule_fiscal | 17 | 26% | merge | `835118E` (14), `587880A` (6), `1064381L` (5), `1403618C` (4), `1028177E` (3), … +12 more |
| SOCIETE AMEUR | matricule_fiscal | 17 | 20% | merge | `1037211P` (9), `1218909A` (6), `1527846Y` (3), `539369W` (3), `647979W` (3), … +12 more |
| SOCIETE AMINA | matricule_fiscal | 17 | 22% | merge | `760439H` (13), `1189215L` (8), `1441290L` (5), `1350590Q` (4), `708427F` (4), … +12 more |
| SOCIETE CIVILE IMMOBILIERE | registre_commerce | 17 | 16% | merge | `B0289792013` (8), `B158341996` (7), `C0155972008` (6), `C0351752007` (6), `B11812003` (3), … +12 more |
| SOCIETE EL-YOSR | matricule_fiscal | 17 | 29% | merge | `1110053J` (15), `1091147F` (4), `1307276L` (4), `1336448A` (4), `1328590J` (3), … +12 more |
| SOCIETE IMEN | matricule_fiscal | 17 | 20% | merge | `418182P` (9), `1114188R` (4), `1254763E` (4), `529053X` (4), `1032358M` (3), … +12 more |
| SOCIETE INTERACTIVE | matricule_fiscal | 17 | 21% | merge | `911130D` (10), `601887V` (7), `985048R` (4), `136242A` (3), `989017B` (3), … +12 more |
| SOCIETE SOLTANA | matricule_fiscal | 17 | 12% | merge | `1421009J` (5), `24120L` (5), `1316992K` (3), `1335434P` (3), `1003017F` (2), … +12 more |
| SOCIETE YESMINE | matricule_fiscal | 17 | 22% | merge | `944007F` (11), `1233140M` (6), `946327D` (4), `1119305Z` (3), `1208232W` (3), … +12 more |
| VENUS | matricule_fiscal | 17 | 24% | merge | `875973K` (12), `1351470M` (8), `1387982A` (4), `1028604C` (3), `1129683E` (3), … +12 more |
| LA TUNISIENNE | matricule_fiscal | 16 | 18% | merge | `536917P` (12), `710611Z` (9), `1332369K` (8), `15175B` (7), `25612G` (7), … +11 more |
| PROMED | matricule_fiscal | 16 | 18% | merge | `1099803A` (7), `1167779A` (4), `710820G` (4), `1160864Q` (3), `916085N` (3), … +11 more |
| SOCIETE CHAIMA | matricule_fiscal | 16 | 32% | merge | `1039666C` (21), `1048157L` (9), `1042834A` (7), `1042634A` (4), `1077374F` (4), … +11 more |
| SOCIETE CIVILE IMMOBILIERE | matricule_fiscal | 16 | 20% | merge | `1196071F` (12), `796816F` (8), `1312254N` (6), `1051362P` (4), `1156121B` (4), … +11 more |
| SOCIETE EL-IZDIHAR | matricule_fiscal | 16 | 12% | merge | `1410368W` (3), `1590329N` (3), `1082967K` (2), `1147337Q` (2), `1241490E` (2), … +11 more |
| SOCIETE EL-KHADRA | matricule_fiscal | 16 | 24% | merge | `1094798A` (13), `6473H` (12), `1276176K` (4), `2301V` (4), `1163497A` (2), … +11 more |
| SOCIETE ENTREPRISE TRABELSI | registre_commerce | 16 | 16% | merge | `B0770222013` (6), `B166081998` (6), `B2510972004` (5), `B1119891998` (4), `B148002000` (3), … +11 more |
| SOCIETE EZDIHAR | matricule_fiscal | 16 | 15% | merge | `1173444R` (6), `1008211C` (4), `743724M` (4), `1197374Y` (3), `1383415E` (3), … +11 more |
| SOCIETE SINDBAD | matricule_fiscal | 16 | 20% | merge | `1464437L` (8), `33420X` (4), `83564Q` (4), `1075736D` (3), `1471358F` (3), … +11 more |
| SOCIETE START | matricule_fiscal | 16 | 22% | merge | `1142207J` (9), `32307S` (4), `1372155T` (3), `1424426L` (3), `1512101J` (3), … +11 more |
| SPEED | registre_commerce | 16 | 19% | merge | `B2434302007` (13), `B123382002` (7), `B01258392016` (6), `B147352002` (6), `B2445292005` (6), … +11 more |
| COMPETENCES+ | matricule_fiscal | 15 | 13% | merge | `1266563M` (5), `984221G` (4), `1225655P` (3), `1225756T` (3), `1281155N` (3), … +10 more |
| LE PROGRES | matricule_fiscal | 15 | 21% | merge | `614801P` (10), `854453Z` (8), `433488V` (5), `1087443G` (4), `1269316L` (3), … +10 more |
| SERA | matricule_fiscal | 15 | 33% | merge | `794807W` (19), `1032633M` (9), `1350321V` (5), `578639R` (5), `806596W` (5), … +10 more |
| SICAV ENTREPRISE | matricule_fiscal | 15 | 21% | merge | `1055155B` (13), `492474R` (7), `492473Q` (6), `770729W` (6), `632956L` (5), … +10 more |
| SOCIETE TUNISIENNE DE COMMERCE | matricule_fiscal | 15 | 22% | merge | `718879M` (7), `1118169F` (4), `1501412M` (3), `1131294Q` (2), `1286985S` (2), … +10 more |
| SOCIETE ZAABI DE TRANSPORT MARCHANDISES | matricule_fiscal | 15 | 17% | merge | `620454D` (7), `33722J` (6), `632995T` (5), `1118622F` (4), `30798S` (4), … +10 more |
| AL BADR | matricule_fiscal | 14 | 19% | merge | `977730G` (6), `1045669T` (3), `1386890S` (3), `1575016J` (3), `789285H` (3), … +9 more |
| AMANA | registre_commerce | 14 | 27% | merge | `B0839012010` (9), `B0112672016` (4), `B2513182011` (4), `B0148462016` (3), `B1681992013` (3), … +9 more |
| CENTRAL | registre_commerce | 14 | 24% | merge | `B0146672013` (11), `B014082007` (7), `B110861996` (5), `B216191302010` (5), `B139782001` (3), … +9 more |
| COSMOS | matricule_fiscal | 14 | 15% | merge | `1013852Q` (5), `1347030L` (4), `1227369V` (3), `1389678D` (3), `1504826V` (3), … +9 more |
| EL AMEL | matricule_fiscal | 14 | 26% | merge | `1014246C` (9), `1105745Y` (4), `609751N` (4), `1290219N` (2), `1392916Y` (2), … +9 more |
| EL AMEL | registre_commerce | 14 | 20% | merge | `B0350862007` (5), `B140191998` (4), `B181321998` (3), `B1112591998` (2), `B114322002` (2), … +9 more |
| EL FATH | matricule_fiscal | 14 | 15% | merge | `1329327Z` (4), `1207994E` (3), `1211370F` (2), `1282808H` (2), `1290516V` (2), … +9 more |
| GALLAND ETABLISSEMENT STABLE | matricule_fiscal | 14 | 38% | merge | `968975B` (14), `1194038W` (5), `1297377H` (3), `1422176D` (3), `765122K` (3), … +9 more |
| LA PRECISION MECANIQUE | matricule_fiscal | 14 | 13% | merge | `1109331W` (4), `967819K` (4), `10420Y` (3), `1033802Q` (2), `1267351F` (2), … +9 more |
| LA SOURCE | matricule_fiscal | 14 | 12% | merge | `1390345A` (3), `1021787W` (2), `1029705L` (2), `1139131F` (2), `1286076M` (2), … +9 more |
| LE FUTURE | registre_commerce | 14 | 31% | merge | `A1314371998` (22), `B02158572012` (9), `B0268932007` (6), `B01141302009` (5), `B0228062006` (5), … +9 more |
| LE MOTEUR | registre_commerce | 14 | 36% | merge | `B8120332013` (14), `B15227622016` (6), `B1541998` (4), `B18161996` (4), `B027182005` (3), … +9 more |
| LE RESEAU | matricule_fiscal | 14 | 18% | merge | `1406193L` (10), `1012896Z` (9), `893431K` (7), `539151D` (5), `1106189W` (4), … +9 more |
| SMC | matricule_fiscal | 14 | 8% | merge | `1045685T` (2), `1153392L` (2), `1319939S` (2), `1382565P` (2), `141769K` (2), … +9 more |
| SOCIETE EL-BARAKA | registre_commerce | 14 | 27% | merge | `B163411996` (8), `B0421852013` (4), `193312000` (3), `B00755262006` (2), `B0174732008` (2), … +9 more |
| SOCIETE LE LABO | registre_commerce | 14 | 17% | merge | `B115761999` (6), `B0225602005` (5), `B2414322011` (5), `B131682003` (3), `A0123122004` (2), … +9 more |
| SOCIETE LE RECOUVREMENT | matricule_fiscal | 14 | 22% | merge | `1116832F` (13), `794031V` (10), `815441C` (10), `817264M` (8), `1432794F` (3), … +9 more |
| SOCIETE LES AMIS | matricule_fiscal | 14 | 18% | merge | `1509857Z` (6), `1296379F` (3), `1415607N` (3), `1459940N` (3), `981321X` (3), … +9 more |
| SOCIETE SIRINE | matricule_fiscal | 14 | 21% | merge | `543776M` (9), `1197390Y` (6), `833559T` (5), `1593035P` (4), `1093680G` (2), … +9 more |
| SOCIETE TROIS | matricule_fiscal | 14 | 20% | merge | `1109574P` (10), `1001583Z` (6), `1158668S` (6), `1533968W` (4), `1175513W` (3), … +9 more |
| SOCIETE ZIED | registre_commerce | 14 | 15% | merge | `B126312000` (3), `B0127782004` (2), `B0722812004` (2), `B117302003` (2), `B15136782011` (2), … +9 more |
| CHAMS | registre_commerce | 13 | 31% | merge | `B144911996` (11), `B2479732007` (4), `B1148231997` (3), `B195301997` (3), `D11637` (3), … +8 more |
| INTERNATIONAL PROD SIGN COMPANY TUNISIA | matricule_fiscal | 13 | 31% | merge | `1142790M` (8), `1410775H` (3), `1074561T` (2), `1102146R` (2), `1169223A` (2), … +8 more |
| LA TUNISIENNE | registre_commerce | 13 | 25% | merge | `B116451996` (14), `B1106841996` (13), `B4481996` (12), `B153661999` (5), `B11645` (3), … +8 more |
| LES HORIZONS | registre_commerce | 13 | 11% | merge | `B01175962009` (3), `B0329022014` (3), `B0412592004` (3), `B15144772013` (3), `B163992005` (3), … +8 more |
| MODA | registre_commerce | 13 | 15% | merge | `B03117592011` (4), `B2417642007` (4), `B24181922009` (3), `A1188671998` (2), `B0240342015` (2), … +8 more |
| RANIM | matricule_fiscal | 13 | 23% | merge | `1351380L` (7), `1116658K` (3), `1105069J` (2), `1210708H` (2), `1214677L` (2), … +8 more |
| SERA | registre_commerce | 13 | 19% | merge | `B131332009` (7), `B2440972012` (6), `B197031996` (5), `143222002` (3), `B137071998` (3), … +8 more |
| SOCIETE ALMA | matricule_fiscal | 13 | 17% | merge | `1539560A` (6), `1113716P` (5), `1139174S` (5), `1190459X` (4), `1366061A` (3), … +8 more |
| SOCIETE ASMA | registre_commerce | 13 | 17% | merge | `B021802004` (4), `B161702001` (4), `B0217302005` (2), `B038132015` (2), `B18862002` (2), … +8 more |
| SOCIETE HAIFA | matricule_fiscal | 13 | 25% | merge | `1130386P` (15), `798547M` (12), `870190N` (8), `939231D` (7), `1605717B` (4), … +8 more |
| SOCIETE LE COIN | registre_commerce | 13 | 23% | merge | `B2418192009` (7), `B01175522014` (4), `B25116352011` (4), `D3115232011` (4), `B01187022016` (2), … +8 more |
| SOCIETE MABROUK | registre_commerce | 13 | 17% | merge | `B0112452009` (6), `B25204972010` (6), `B2528782007` (6), `B01119922009` (3), `144021997` (2), … +8 more |
| SOCIETE SARAH AND CO | matricule_fiscal | 13 | 11% | merge | `1078067B` (3), `1173935G` (3), `1092577E` (2), `1130904P` (2), `1285816W` (2), … +8 more |
| SOCIETE UNIQUE | registre_commerce | 13 | 35% | merge | `B16242002` (12), `B0317982005` (7), `B1116671996` (2), `B13211392010` (2), `B1547832005` (2), … +8 more |
| SOGECO | matricule_fiscal | 13 | 17% | merge | `2011M` (5), `1425086Q` (4), `1042231C` (3), `1042241E` (3), `411618R` (3), … +8 more |
| AGRICO | matricule_fiscal | 12 | 14% | merge | `745053D` (3), `998159R` (3), `1136515F` (2), `1514794K` (2), `1547041C` (2), … +7 more |
| CESAR | matricule_fiscal | 12 | 14% | merge | `1161879C` (3), `1108533A` (2), `1277770C` (2), `13781301K` (2), `1408088V` (2), … +7 more |
| EL HANA | matricule_fiscal | 12 | 17% | merge | `987297R` (4), `1164832Z` (3), `1170763R` (2), `1324901L` (2), `1409852F` (2), … +7 more |
| EL HOUDA | registre_commerce | 12 | 17% | merge | `B2526902007` (6), `B117391999` (5), `B1692472016` (4), `B17391` (4), `B111299199` (3), … +7 more |
| EL MANAR | matricule_fiscal | 12 | 16% | merge | `326140T` (5), `596677A` (5), `1473249K` (4), `1021065R` (2), `1213689L` (2), … +7 more |
| EL WAFA | matricule_fiscal | 12 | 14% | merge | `1042438A` (3), `1014358K` (2), `1229384C` (2), `1403054M` (2), `1451246M` (2), … +7 more |
| EL WIFEK | registre_commerce | 12 | 29% | merge | `B129781996` (6), `B026492005` (2), `B0514372009` (2), `B09231232015` (2), `B26138392010` (2), … +7 more |
| EMNA | registre_commerce | 12 | 31% | merge | `B01109232009` (10), `B0265732006` (5), `B1122491997` (4), `B0821262006` (3), `B136632002` (2), … +7 more |
| LE PILOTE | matricule_fiscal | 12 | 21% | merge | `37603V` (6), `1603785F` (4), `1195167J` (3), `837803V` (3), `1320768H` (2), … +7 more |
| SAAD | registre_commerce | 12 | 22% | merge | `B0376762010` (5), `B2451272011` (4), `B01212932017` (2), `B13211998` (2), `B19225352017` (2), … +7 more |
| SELECTION | registre_commerce | 12 | 21% | merge | `D3125697` (6), `B24219442011` (5), `B2452082007` (4), `B0122980201` (2), `B0813122005` (2), … +7 more |
| SOCIETE AMANI | matricule_fiscal | 12 | 21% | merge | `1455335E` (5), `515524K` (4), `1053292B` (2), `1274815K` (2), `1424340F` (2), … +7 more |
| SOCIETE DELIVERY | matricule_fiscal | 12 | 29% | merge | `983313F` (15), `432912K` (12), `1794326Q` (6), `1471967B` (5), `1139138N` (2), … +7 more |
| SOCIETE EL-AMAL | matricule_fiscal | 12 | 43% | merge | `944132K` (15), `1395085W` (5), `1013643H` (2), `1232701V` (2), `1285783E` (2), … +7 more |
| SOCIETE EL-MAJD | matricule_fiscal | 12 | 31% | merge | `1427173X` (8), `1077297K` (3), `1131592Y` (2), `1143920H` (2), `1181034Y` (2), … +7 more |
| SOCIETE ETABLISSEMENT TRIKI | matricule_fiscal | 12 | 32% | merge | `953213L` (8), `1085881S` (2), `1131439P` (2), `1158872V` (2), `1347391K` (2), … +7 more |
| SOCIETE EZZAHRA | matricule_fiscal | 12 | 21% | merge | `1392733S` (5), `356712A` (4), `1071398N` (2), `1193099F` (2), `1457726A` (2), … +7 more |
| SOCIETE HENDA | matricule_fiscal | 12 | 36% | merge | `430134G` (8), `851494W` (3), `1481224X` (2), `1556919K` (2), `44754C` (2), … +7 more |
| SOCIETE M | registre_commerce | 12 | 25% | merge | `B0731462015` (7), `9171042013` (3), `B0171042013` (3), `B2761102011` (3), `B01239262013` (2), … +7 more |
| SOCIETE SARAH | matricule_fiscal | 12 | 15% | merge | `613864B` (4), `1423521E` (3), `307159Z` (3), `125124Q` (2), `1304100Y` (2), … +7 more |
| SOCIETE SLAMA | matricule_fiscal | 12 | 16% | merge | `1173981N` (6), `1202915R` (6), `1283594S` (4), `566070G` (4), `899435Q` (4), … +7 more |
| SOMAC | matricule_fiscal | 12 | 20% | merge | `1048884M` (5), `1173161H` (3), `1184741H` (3), `894317N` (3), `1154275L` (2), … +7 more |
| BRAVO | matricule_fiscal | 11 | 29% | merge | `858784J` (18), `1179783K` (13), `1147350M` (7), `1335480W` (5), `811575Z` (5), … +6 more |
| DEFI | matricule_fiscal | 11 | 17% | merge | `1168147B` (4), `1549454E` (4), `1147213D` (3), `1018979C` (2), `1436206P` (2), … +6 more |
| DISCOVERY | matricule_fiscal | 11 | 17% | merge | `955323A` (4), `971451B` (4), `1124325M` (2), `1125906H` (2), `1298513B` (2), … +6 more |
| ENNASR | matricule_fiscal | 11 | 17% | merge | `872688V` (4), `896345B` (4), `1189435X` (3), `1221226Q` (2), `1238813P` (2), … +6 more |
| LA PERLE | registre_commerce | 11 | 18% | merge | `B24131522011` (4), `B127602003` (3), `B249555` (3), `B01198592013` (2), `B0850142004` (2), … +6 more |
| LEILA | matricule_fiscal | 11 | 25% | merge | `307285E` (7), `578841R` (6), `1134528C` (4), `1221863D` (2), `1370973N` (2), … +6 more |
| MAYA | registre_commerce | 11 | 17% | merge | `B192902000` (3), `B01148352010` (2), `B01208322018` (2), `B0493572007` (2), `B2045222005` (2), … +6 more |
| NOUR DE COMMERCE | matricule_fiscal | 11 | 22% | merge | `1011690G` (6), `1202168E` (3), `1213637Y` (2), `1223534X` (2), `1418789Z` (2), … +6 more |
| SOCIETE ADEM | registre_commerce | 11 | 14% | merge | `B09173892013` (3), `B195422007` (3), `B197691998` (3), `B40165582015` (3), `1612662015` (2), … +6 more |
| SOCIETE AMINA | registre_commerce | 11 | 21% | merge | `B0151652006` (8), `B1154371997` (7), `B158762002` (5), `B15876202` (4), `B3135242011` (4), … +6 more |
| SOCIETE DE COMMERCE INTERNATIONAL | matricule_fiscal | 11 | 17% | merge | `1040118T` (5), `1036844P` (4), `1419272C` (4), `982996R` (4), `1189910D` (2), … +6 more |
| SOCIETE GLOBE | registre_commerce | 11 | 21% | merge | `B1112171996` (8), `B0222602008` (5), `B31164402012` (5), `B2415782007` (4), `B245492007` (4), … +6 more |
| SOCIETE MODERNE DE BATIMENT | matricule_fiscal | 11 | 14% | merge | `1303517R` (4), `1305051L` (4), `1420980R` (4), `1495847X` (3), `999313M` (3), … +6 more |
| SOCIETE NOUR | registre_commerce | 11 | 22% | merge | `B150052001` (7), `B51118782013` (6), `B0421112005` (5), `B15186122009` (3), `B156161997` (3), … +6 more |
| SOCIETE ZAABI DE TRANSPORT MARCHANDISES | registre_commerce | 11 | 15% | merge | `B1142411997` (4), `B117461997` (4), `B04204162011` (3), `B110761996` (3), `B163491999` (3), … +6 more |
| ARC EN CIEL | registre_commerce | 10 | 29% | merge | `B2077192012` (6), `B131681997` (4), `B03214882012` (2), `B1539592014` (2), `B164831997` (2), … +5 more |
| ARTEMIS | matricule_fiscal | 10 | 46% | merge | `1030529E` (19), `1237666G` (6), `1049050E` (4), `1191969V` (3), `1213487C` (2), … +5 more |
| EL ALIA | matricule_fiscal | 10 | 24% | merge | `1223544Z` (8), `1226289R` (5), `1472185G` (4), `1501398H` (4), `1144359J` (3), … +5 more |
| EL FAOUZ | registre_commerce | 10 | 42% | merge | `B2557942007` (13), `A164311999` (7), `B08672004` (2), `B145921997` (2), `D025942013` (2), … +5 more |
| ENNAJEH | matricule_fiscal | 10 | 21% | merge | `319263M` (5), `918476J` (4), `1146381Q` (3), `1068729J` (2), `1198243R` (2), … +5 more |
| FARAH | matricule_fiscal | 10 | 31% | merge | `38228W` (11), `843718W` (5), `1308046C` (4), `1108075V` (3), `1000975H` (2), … +5 more |
| INTERNATIONAL PROD SIGN COMPANY TUNISIA | registre_commerce | 10 | 18% | merge | `B01136842015` (3), `B2489642008` (3), `801166832010` (2), `B0144732009` (2), `B2479212008` (2), … +5 more |
| KMG SERVICES | matricule_fiscal | 10 | 33% | merge | `1364584Q` (9), `1231141E` (2), `1270427J` (2), `1306352B` (2), `1321442R` (2), … +5 more |
| SOCIETE DE NUTRITION | registre_commerce | 10 | 39% | merge | `B132882003` (9), `B08253752017` (3), `B117812001` (2), `B15132272009` (2), `B162631999` (2), … +5 more |
| SOCIETE D’ETUDES ET DE DEVELOPPEMENT TOURISTIQUE SODET SUD | matricule_fiscal | 10 | 44% | merge | `1315534G` (10), `866191K` (3), `1268203Y` (2), `1379912N` (2), `1428451E` (1), … +5 more |
| SOCIETE IMMOBILIERE | matricule_fiscal | 10 | 38% | merge | `762750W` (12), `1525744J` (6), `411858G` (3), `1355558M` (2), `1442412G` (2), … +5 more |
| SOCIETE INES | registre_commerce | 10 | 42% | merge | `B1123611997` (10), `B0152592005` (4), `B170051998` (2), `B2424092005` (2), `A20173582012` (1), … +5 more |
| SOCIETE JAWHARA | registre_commerce | 10 | 36% | merge | `B1132801997` (10), `B07187442011` (5), `B0911802006` (2), `B0912011` (2), `B09411582014` (2), … +5 more |
| SOCIETE JMF | matricule_fiscal | 10 | 17% | merge | `1089766H` (3), `1020630Q` (2), `1038396V` (2), `1181281M` (2), `1372202H` (2), … +5 more |
| SOCIETE LE LIVRE | matricule_fiscal | 10 | 18% | merge | `1598Z` (3), `975957R` (3), `1485198F` (2), `1597213G` (2), `580387L` (2), … +5 more |
| SOCIETE LINA | matricule_fiscal | 10 | 11% | merge | `1153592S` (2), `1187977Q` (2), `1224096A` (2), `1300655N` (2), `1364799E` (2), … +5 more |
| SOCIETE MS CONSULTING | matricule_fiscal | 10 | 15% | merge | `1319354X` (3), `1408196Y` (3), `1025489F` (2), `1193201J` (2), `1255148Q` (2), … +5 more |
| SOCIETE OCTOPUS | matricule_fiscal | 10 | 17% | merge | `1103781T` (3), `1164990N` (2), `1191170L` (2), `1491590Y` (2), `1495147Z` (2), … +5 more |
| SOCIETE SINDBAD | registre_commerce | 10 | 19% | merge | `B141821997` (4), `B0151462005` (3), `B171181997` (3), `B120341997` (2), `B158252000` (2), … +5 more |
| SOCIETE TAAMIR | matricule_fiscal | 10 | 28% | merge | `896331V` (7), `1058083Q` (3), `1213115M` (3), `1235254F` (2), `1354036K` (2), … +5 more |
| SOCIETE TRAVAUX ET SERVICES | matricule_fiscal | 10 | 21% | merge | `1339452J` (5), `969478S` (5), `1495308Y` (4), `1106088R` (2), `1422672Q` (2), … +5 more |
| STEP | registre_commerce | 10 | 54% | merge | `B2440682006` (21), `B27108092012` (6), `B0925691007` (2), `B0925692007` (2), `B119192003` (2), … +5 more |
| TAYSIR | matricule_fiscal | 10 | 20% | merge | `1202048X` (6), `1350779C` (6), `1446999Q` (3), `1594039Y` (3), `1202708L` (2), … +5 more |
| TUNISIE TRAVAUX | matricule_fiscal | 10 | 18% | merge | `857921V` (6), `111269V` (5), `838552H` (4), `1112692V` (3), `1191070H` (3), … +5 more |
| AGENCE EL-AMANA IMMOBILIERE AEL | matricule_fiscal | 9 | 19% | merge | `1071452B` (3), `1182883N` (2), `1292857Y` (2), `1350141S` (2), `1566999H` (2), … +4 more |
| AGORA | matricule_fiscal | 9 | 24% | merge | `985808J` (7), `1164697L` (5), `1297218S` (4), `1310651P` (3), `892401Z` (3), … +4 more |
| FLORENCE | matricule_fiscal | 9 | 21% | merge | `9934691G` (5), `983662A` (4), `1031730N` (3), `496239Z` (3), `583987T` (3), … +4 more |
| GENERAL MAGHREB SERVICES | matricule_fiscal | 9 | 54% | merge | `900648W` (40), `764626B` (13), `1024399A` (6), `901487B` (6), `1334343H` (4), … +4 more |
| L'OLIVIER BLEU DE RESTAURATION ET DE LOISIRS | matricule_fiscal | 9 | 26% | merge | `960643Y` (6), `822681K` (4), `1191422M` (3), `1210944T` (2), `1211004K` (2), … +4 more |
| LE BON GOUT | matricule_fiscal | 9 | 25% | merge | `620509B` (5), `1312192R` (3), `1231179V` (2), `1286002S` (2), `1332750L` (2), … +4 more |
| MANUF TUNISIENNE DES SERRURES MTS | matricule_fiscal | 9 | 31% | merge | `45372W` (9), `1159808Q` (5), `1174778R` (4), `1245379Z` (4), `1459958Z` (2), … +4 more |
| PLASTICS | matricule_fiscal | 9 | 60% | merge | `12866K` (22), `889956G` (5), `1324701E` (3), `1361122Z` (2), `1125315P` (1), … +4 more |
| PRESTIGE | matricule_fiscal | 9 | 30% | merge | `1025936H` (7), `340668H` (4), `1135848V` (2), `1325471P` (2), `1379288M` (2), … +4 more |
| SOCIETE ALFA | registre_commerce | 9 | 27% | merge | `B134092000` (4), `B2459002006` (3), `B24106062009` (2), `A09186692010` (1), `A0924652013` (1), … +4 more |
| SOCIETE DE MAINTENANCE EL-FERDAOUS | matricule_fiscal | 9 | 26% | merge | `925137J` (8), `1299241A` (5), `1105228F` (4), `1201600V` (3), `6236487A` (3), … +4 more |
| SOCIETE DINA | matricule_fiscal | 9 | 19% | merge | `1253454P` (3), `1384029C` (3), `1328329X` (2), `1360179N` (2), `1519701J` (2), … +4 more |
| SOCIETE EL-ANDALOUS | matricule_fiscal | 9 | 35% | merge | `1284993J` (9), `552442S` (4), `1223538B` (2), `1453620Y` (2), `1541120Z` (2), … +4 more |
| SOCIETE ESSAADA | matricule_fiscal | 9 | 21% | merge | `449637W` (4), `881688W` (4), `10305W` (2), `1318653B` (2), `1486299P` (2), … +4 more |
| SOCIETE GENERALE TRAVAUX | matricule_fiscal | 9 | 22% | merge | `907437R` (7), `906938E` (6), `1539079W` (5), `781271R` (4), `413710V` (3), … +4 more |
| SOCIETE HENDA | registre_commerce | 9 | 30% | merge | `191521997` (5), `B154871997` (4), `B191521997` (4), `D034672006` (2), `191421997` (1), … +4 more |
| SOCIETE IMEM | matricule_fiscal | 9 | 24% | merge | `1321429V` (5), `639495H` (3), `1040053T` (2), `1140372N` (2), `1418589S` (2), … +4 more |
| SOCIETE IMEN | registre_commerce | 9 | 20% | merge | `B1114021997` (4), `B161012001` (4), `B0863912007` (2), `B1044782014` (2), `B111802002` (2), … +4 more |
| SOCIETE IRIS | registre_commerce | 9 | 18% | merge | `B138592001` (3), `B248782008` (3), `19582001` (2), `B01173282013` (2), `B07101342009` (2), … +4 more |
| SOCIETE NADINE + | matricule_fiscal | 9 | 35% | merge | `635831L` (8), `1121398S` (2), `1151556E` (2), `1219842C` (2), `1332594S` (2), … +4 more |
| SOCIETE RIHAB | matricule_fiscal | 9 | 40% | merge | `644742M` (12), `22762H` (5), `1006590V` (2), `1197481A` (2), `1253930X` (2), … +4 more |
| SOCIETE RISTORANTE ITALIANO LA PERLA NERA | matricule_fiscal | 9 | 38% | merge | `1021766Q` (10), `1096227B` (4), `1221590X` (2), `1262445P` (2), `1298591R` (2), … +4 more |
| SOCIETE SAMAR | matricule_fiscal | 9 | 12% | merge | `1012573G` (2), `1273275Z` (2), `1292714H` (2), `1366668C` (2), `1406497A` (2), … +4 more |
| SOCIETE TUNISIENNE DELECTRO PORTATIF | matricule_fiscal | 9 | 33% | merge | `822993Z` (11), `889901Q` (5), `1277591B` (4), `802083G` (4), `1373454G` (3), … +4 more |
| SOCIETE TUNISIENNE DELECTRO PORTATIF | registre_commerce | 9 | 26% | merge | `B14082003` (11), `B179411996` (11), `B0939632004` (5), `B01239272012` (4), `B137282002` (4), … +4 more |
| STUDI | matricule_fiscal | 9 | 27% | merge | `1031438G` (11), `1023394Q` (9), `1227137E` (7), `1328566J` (6), `1123613M` (2), … +4 more |
| DALIA | matricule_fiscal | 8 | 23% | merge | `1292725L` (3), `944116K` (3), `1203453L` (2), `1381117N` (1), `1417989B` (1), … +3 more |
| ERRAHMA | registre_commerce | 8 | 80% | merge | `B0319512007` (67), `B2538722005` (7), `B180561997` (5), `B0193162015` (2), `80319512007` (1), … +3 more |
| GENERAL MAGHREB SERVICES | registre_commerce | 8 | 76% | merge | `B0855112004` (36), `B221452005` (7), `B24246442006` (3), `B0123152014` (2), `B0856112004` (2), … +3 more |
| ILEF | matricule_fiscal | 8 | 18% | merge | `1193680N` (3), `492443J` (3), `1465231C` (2), `1488166K` (2), `1543543D` (2), … +3 more |
| INTERNATIONAL TELE CONSULTANTS | matricule_fiscal | 8 | 31% | merge | `1184858W` (8), `1094354Z` (5), `1482995Q` (5), `1009813D` (3), `1025880S` (2), … +3 more |
| LA GENERALE DE DISTRIBUTION | matricule_fiscal | 8 | 28% | merge | `972084C` (4), `1250085W` (3), `895053M` (3), `1110385C` (2), `1282163S` (2), … +3 more |
| LA MEDITERRANEENNE | matricule_fiscal | 8 | 24% | merge | `1043200Z` (4), `1292534F` (3), `1131153C` (2), `1161612A` (2), `1275145Y` (2), … +3 more |
| MAGHREB INTERNATIONAL PUBLICITE MIP | registre_commerce | 8 | 48% | merge | `B0167672008` (19), `B19582003` (5), `B2410942004` (4), `B2510052009` (4), `B0181482008` (3), … +3 more |
| MARAM SERVICE | matricule_fiscal | 8 | 23% | merge | `1382020J` (5), `1262150B` (4), `1531233C` (4), `1076946R` (2), `1436764R` (2), … +3 more |
| PNEU | registre_commerce | 8 | 48% | merge | `B11242002` (12), `B164531998` (5), `B15178472010` (2), `B1589712008` (2), `B0220392007` (1), … +3 more |
| PREMIUM | registre_commerce | 8 | 20% | merge | `133202001` (4), `B24199182010` (4), `B133202001` (3), `B01173652012` (2), `B04212132015` (2), … +3 more |
| ROMA | matricule_fiscal | 8 | 19% | merge | `1076157T` (3), `1149374E` (3), `1195899Q` (2), `1311543Q` (2), `1455675Y` (2), … +3 more |
| SOCIETE ALIM | matricule_fiscal | 8 | 27% | merge | `1284688C` (4), `1181898R` (2), `1230692D` (2), `1504536M` (2), `37744H` (2), … +3 more |
| SOCIETE ANIS | registre_commerce | 8 | 17% | merge | `B0967172007` (2), `B24227262010` (2), `B3175472009` (2), `B51231832016` (2), `A01161932015` (1), … +3 more |
| SOCIETE BAYA | registre_commerce | 8 | 33% | merge | `B09206802012` (4), `B2514412004` (2), `B01203742017` (1), `B0198092010` (1), `B0321252011` (1), … +3 more |
| SOCIETE DE COMMERCE INTERNATIONAL | registre_commerce | 8 | 17% | merge | `B03124532013` (2), `B15177012015` (2), `B24190722011` (2), `B243782008` (2), `B0220522015` (1), … +3 more |
| SOCIETE DE REPARATION ET DE MAINTENANCE SRM | matricule_fiscal | 8 | 20% | merge | `1353674G` (3), `1209446N` (2), `1412122H` (2), `1445160T` (2), `1474605P` (2), … +3 more |
| SOCIETE DINA | registre_commerce | 8 | 35% | merge | `B150351998` (7), `B119892001` (6), `B158631988` (3), `B158661998` (3), `8150351998` (2), … +3 more |
| SOCIETE EL-BADR | matricule_fiscal | 8 | 41% | merge | `900571R` (9), `1028408A` (2), `1105185M` (2), `13868905A` (2), `1425475A` (2), … +3 more |
| SOCIETE EL-IZDIHAR | registre_commerce | 8 | 33% | merge | `B19251997` (6), `B0247972008` (4), `B143772001` (2), `B265402009` (2), `B0143822005` (1), … +3 more |
| SOCIETE EVENT | registre_commerce | 8 | 37% | merge | `B158082002` (15), `B131892002` (11), `B01215832016` (3), `B0177802016` (3), `B1144011997` (3), … +3 more |
| SOCIETE GENERALE MAKNI DE COMMERCE GMC | matricule_fiscal | 8 | 54% | merge | `900647V` (13), `1093450T` (2), `1328471C` (2), `1331285C` (2), `1341295K` (2), … +3 more |
| SOCIETE HASNA | matricule_fiscal | 8 | 23% | merge | `917596M` (7), `1158996G` (5), `1433214B` (5), `760968E` (4), `1201933P` (3), … +3 more |
| SOCIETE IMMOBILIERE | registre_commerce | 8 | 42% | merge | `B2420782004` (8), `B01158012017` (2), `B143291997` (2), `B158921996` (2), `B2420002006` (2), … +3 more |
| SOCIETE OLIVA | matricule_fiscal | 8 | 36% | merge | `1327542W` (11), `578644N` (8), `814700Y` (3), `1258632L` (2), `1397256F` (2), … +3 more |
| SOCIETE SMS | matricule_fiscal | 8 | 48% | merge | `1141630R` (12), `1045375G` (3), `1100483Y` (2), `1274374F` (2), `765046Q` (2), … +3 more |
| SOCIETE TAAMIR | registre_commerce | 8 | 33% | merge | `B187191996` (8), `B0948382004` (4), `B143142002` (4), `B181791996` (3), `B201042008` (2), … +3 more |
| SOCIETE TUNISIENNE DE SERVICES | matricule_fiscal | 8 | 44% | merge | `886782P` (11), `1336481B` (3), `1129804V` (2), `1216838T` (2), `1219184Q` (2), … +3 more |
| SOCIETE YOSR | registre_commerce | 8 | 26% | merge | `B113341997` (6), `B0133332008` (5), `B0220922016` (3), `B0268982016` (3), `B01167772014` (2), … +3 more |
| SOCIETES ANONYMES SOCIETE TUNISIAN CONTINENTAL HOTELS TUCOTEL | matricule_fiscal | 8 | 29% | merge | `1276692B` (8), `758138B` (7), `9439T` (6), `1237132E` (2), `1408877S` (2), … +3 more |
| SOGEBAT | matricule_fiscal | 8 | 29% | merge | `745998X` (4), `1439263M` (2), `1501115F` (2), `1564500G` (2), `104498J` (1), … +3 more |
| STPA | matricule_fiscal | 8 | 51% | merge | `495907J` (26), `635629L` (11), `1021569M` (4), `1097835A` (3), `1001804S` (2), … +3 more |
| ACCESSOIRES TEXTILES COMPANY ATC | matricule_fiscal | 7 | 50% | merge | `836930F` (11), `1256267B` (2), `1282365B` (2), `1376096S` (2), `1551001Y` (2), … +2 more |
| AGRIMED | matricule_fiscal | 7 | 44% | merge | `583952G` (15), `974426N` (12), `1496292M` (2), `1558373F` (2), `1455672V` (1), … +2 more |
| AZIZA | registre_commerce | 7 | 39% | merge | `B09181872009` (7), `B31144042012` (3), `B0897792018` (2), `B1103281997` (2), `D14282006` (2), … +2 more |
| BANQUE DE TUNISIE BT | matricule_fiscal | 7 | 56% | merge | `120H` (15), `121J` (5), `1385594H` (2), `15094B` (2), `496311P` (1), … +2 more |
| BANQUE DE TUNISIE BT | registre_commerce | 7 | 46% | merge | `B140811997` (31), `B1105941996` (14), `B14081` (7), `B1163511197` (6), `B1163511997` (5), … +2 more |
| BATIMENT ET TRAVAUX PUBLICS | matricule_fiscal | 7 | 33% | merge | `1414945A` (9), `571229W` (5), `1127460G` (4), `1593369K` (3), `433032P` (3), … +2 more |
| BB | registre_commerce | 7 | 43% | merge | `B0126342006` (6), `B2413162006` (3), `0029872018` (1), `B01192322016` (1), `B02124052015` (1), … +2 more |
| BRAVO | registre_commerce | 7 | 30% | merge | `B27622004` (10), `B0322962010` (6), `B149962002` (5), `B13402001` (4), `B03222962010` (3), … +2 more |
| CIE TUNISIENNE DES SACS CTS | registre_commerce | 7 | 46% | merge | `B19711998` (10), `B133171996` (8), `B24142122009` (5), `D19711998` (2), `B0132942008` (1), … +2 more |
| COGEM + | matricule_fiscal | 7 | 60% | merge | `34378S` (21), `418487E` (7), `1353488G` (3), `1278879V` (1), `32593P` (1), … +2 more |
| DISSOLUTION SUITE A LA FUSION ABSORPTION DE LA SOCIETE | matricule_fiscal | 7 | 25% | merge | `1414402X` (3), `1234935W` (2), `1270168J` (2), `1573674F` (2), `1495864Y` (1), … +2 more |
| ECOLE PRIVEE EL-IMTIEZ | matricule_fiscal | 7 | 66% | merge | `433775Z` (31), `515159J` (4), `864415Y` (4), `1412067E` (2), `1518775Z` (2), … +2 more |
| EL FATH | registre_commerce | 7 | 31% | merge | `B0811742014` (4), `B03149452011` (3), `C1381198` (2), `1612848201` (1), `B0776802011` (1), … +2 more |
| ESSALEM | matricule_fiscal | 7 | 52% | merge | `1036121J` (25), `576240M` (7), `470858K` (6), `956062C` (6), `1357866F` (2), … +2 more |
| FLOWER | matricule_fiscal | 7 | 56% | merge | `5924K` (9), `1139107F` (2), `1520333W` (2), `1530393P` (2), `1329330T` (1), … +2 more |
| HAFEDH | matricule_fiscal | 7 | 50% | merge | `1187574Z` (11), `1186453L` (4), `1008727C` (2), `1590073H` (2), `10190311K` (1), … +2 more |
| JUNIOR | registre_commerce | 7 | 28% | merge | `B0174932007` (7), `B0757932005` (6), `B2550202006` (4), `B0183352013` (3), `B036602009` (3), … +2 more |
| KZ PETROLEUM SERVICES | matricule_fiscal | 7 | 46% | merge | `605157H` (18), `1178536R` (6), `398144V` (5), `1134803C` (3), `1402704V` (3), … +2 more |
| L'OLIVIER BLEU DE RESTAURATION ET DE LOISIRS | registre_commerce | 7 | 41% | merge | `B2447342011` (7), `B01229412012` (2), `B07143242011` (2), `B14052003` (2), `B25149432011` (2), … +2 more |
| LA CONFIANCE | matricule_fiscal | 7 | 18% | merge | `1141087Q` (2), `1186258K` (2), `1352135D` (2), `1528577A` (2), `1546059J` (1), … +2 more |
| LA FONDATION | registre_commerce | 7 | 50% | merge | `B123212003` (14), `B243052005` (4), `B0180532007` (3), `B124022001` (3), `B0173772010` (2), … +2 more |
| LA FONTAINE DU SAVOIR | matricule_fiscal | 7 | 20% | merge | `1301559T` (3), `1245000P` (2), `1269619Z` (2), `1468933Q` (2), `1484441S` (2), … +2 more |
| LA PRINCESSE | matricule_fiscal | 7 | 29% | merge | `1343871E` (7), `1431975E` (5), `1185113N` (3), `830842F` (3), `1276030R` (2), … +2 more |
| LA SIRENE | matricule_fiscal | 7 | 26% | merge | `1366894L` (5), `997987S` (5), `1119848C` (3), `624486E` (3), `1094410P` (1), … +2 more |
| LA SOURCE | registre_commerce | 7 | 30% | merge | `B24124862009` (6), `B0269052008` (5), `B15103912010` (3), `B01203712012` (2), `B016502013` (2), … +2 more |
| LE RESEAU | registre_commerce | 7 | 38% | merge | `B2451512007` (11), `02115312015` (10), `B0178212008` (2), `B0365002013` (2), `B91207972012` (2), … +2 more |
| MANAGER | matricule_fiscal | 7 | 32% | merge | `796017F` (7), `549184N` (4), `1573253M` (3), `791031G` (3), `1380839N` (2), … +2 more |
| MARHABA | matricule_fiscal | 7 | 27% | merge | `989509S` (6), `1091550N` (4), `1200451W` (3), `1595009W` (3), `1312583D` (2), … +2 more |
| MC CONSULTING | matricule_fiscal | 7 | 50% | merge | `1173994T` (11), `1275241X` (2), `1431619L` (2), `1457616V` (2), `1582485D` (2), … +2 more |
| ME CONSULTANTS | registre_commerce | 7 | 57% | merge | `B0323562004` (17), `B08100642013` (5), `B125042003` (3), `B12732001` (2), `B0123492004` (1), … +2 more |
| METALCO | matricule_fiscal | 7 | 22% | merge | `1257855W` (4), `46793T` (4), `623899T` (4), `635539K` (2), `924057F` (2), … +2 more |
| NOURTEX CONFECTION | matricule_fiscal | 7 | 29% | merge | `580168B` (5), `1248880W` (4), `1326235H` (2), `1439806X` (2), `878813G` (2), … +2 more |
| R M ELEGANCE | matricule_fiscal | 7 | 17% | merge | `1124391Y` (2), `1280979T` (2), `1422288L` (2), `1501241L` (2), `1542277A` (2), … +2 more |
| SARA SERVICES | matricule_fiscal | 7 | 21% | merge | `450401S` (3), `1256558K` (2), `1273536B` (2), `1277959P` (2), `1390519E` (2), … +2 more |
| SATEX | matricule_fiscal | 7 | 27% | merge | `1002394A` (3), `1566925N` (2), `1590166M` (2), `1533210J` (1), `635890N` (1), … +2 more |
| SOCIETE ANONYME IMMOBILIERE DU NORD DE LA TUNISIE | registre_commerce | 7 | 70% | merge | `B1134041997` (26), `B119041998` (3), `B0152672004` (2), `B187921996` (2), `B6151996` (2), … +2 more |
| SOCIETE DE SERVICES ADMINISTRATIFS | matricule_fiscal | 7 | 19% | merge | `1263617W` (3), `1287162N` (3), `1351090D` (2), `1450253G` (2), `1476641C` (2), … +2 more |
| SOCIETE EL-ANDALOUS | registre_commerce | 7 | 39% | merge | `B023142013` (7), `B1513311998` (4), `B144061999` (3), `231412013` (1), `B0231412012` (1), … +2 more |
| SOCIETE EL-BADR | registre_commerce | 7 | 45% | merge | `B081072005` (9), `B0853472008` (3), `80728562015` (2), `B16691999` (2), `B2599272009` (2), … +2 more |
| SOCIETE EL-WIFAK | registre_commerce | 7 | 25% | merge | `B1124851997` (4), `B9150152012` (3), `R164762000` (3), `B085072006` (2), `D014062010` (2), … +2 more |
| SOCIETE EL-YOSR | registre_commerce | 7 | 52% | merge | `B27116112009` (15), `B1339142014` (4), `B08212014` (3), `B1010582016` (2), `B2456942007` (2), … +2 more |
| SOCIETE ELEMENTS + | matricule_fiscal | 7 | 25% | merge | `1307434G` (4), `853204D` (4), `1573509S` (2), `1586756A` (2), `496781S` (2), … +2 more |
| SOCIETE ETABLISSEMENT TRIKI | registre_commerce | 7 | 31% | merge | `B19311997` (4), `B0386292014` (2), `B1100761996` (2), `B4014222010` (2), `A14179932013` (1), … +2 more |
| SOCIETE GENERALE DE QUINCAILLERIE | matricule_fiscal | 7 | 17% | merge | `1064715N` (2), `1121989L` (2), `1205922D` (2), `1230885L` (2), `1561748S` (2), … +2 more |
| SOCIETE GOLDEN SAPHIR | matricule_fiscal | 7 | 20% | merge | `1218390Q` (2), `1316506G` (2), `1397520C` (2), `1247221K` (1), `1270038Z` (1), … +2 more |
| SOCIETE IDEAL CONFECTION | matricule_fiscal | 7 | 26% | merge | `459621S` (5), `1296797W` (4), `1031120L` (3), `1313127L` (3), `1513157F` (2), … +2 more |
| SOCIETE INSIDE | matricule_fiscal | 7 | 37% | merge | `1191348V` (7), `993758N` (3), `1221610H` (2), `1458775P` (2), `1595441J` (2), … +2 more |
| SOCIETE INTERNATIONAL TRADING COMPANY | matricule_fiscal | 7 | 33% | merge | `1432918Z` (11), `1238613X` (7), `1189076T` (4), `31475E` (4), `1135447G` (3), … +2 more |
| SOCIETE INTERPROFESSIONNELLE POUR LA COMPENSATION ET LE DEPOT DES VALEURS MOBILIERES STICODEVAM | registre_commerce | 7 | 39% | merge | `B163781996` (19), `B16378` (14), `B112092001` (6), `B114761996` (6), `B0187252017` (2), … +2 more |
| SOCIETE LES AMIS | registre_commerce | 7 | 26% | merge | `B2684272017` (5), `B08159302015` (3), `B15137462016` (3), `B187452013` (3), `B119482002` (2), … +2 more |
| SOCIETE MOLKA ET MARIEM | matricule_fiscal | 7 | 22% | merge | `1053356A` (4), `584129L` (4), `1311872F` (2), `1446528L` (2), `1480694W` (2), … +2 more |
| SOCIETE MULTISERVICES | registre_commerce | 7 | 20% | merge | `B0159532006` (2), `B0178222008` (2), `B1128441997` (2), `B0863152006` (1), `B20159902010` (1), … +2 more |
| SOCIETE NARJES | matricule_fiscal | 7 | 28% | merge | `487745M` (5), `505776Z` (4), `610315M` (3), `1037835S` (2), `817570V` (2), … +2 more |
| SOCIETE NEJMA CONFECTION | matricule_fiscal | 7 | 24% | merge | `1483879R` (4), `718567Y` (4), `14833879R` (3), `1051248N` (2), `1490213V` (2), … +2 more |
| SOCIETE NERMINE | matricule_fiscal | 7 | 15% | merge | `1228163L` (2), `1276633P` (2), `1291549J` (2), `1482986P` (2), `1596251J` (2), … +2 more |
| SOCIETE NOUVELLE DE BRASSERIE | matricule_fiscal | 7 | 36% | merge | `940993H` (26), `644969F` (21), `17216B` (13), `856056Y` (10), `17216R` (2), … +2 more |
| SOCIETE NOUVELLE DE BRASSERIE | registre_commerce | 7 | 31% | merge | `B0120492006` (19), `B182181999` (18), `B153482003` (10), `B145281999` (6), `B154281999` (6), … +2 more |
| SOCIETE SMART SPECTRA | matricule_fiscal | 7 | 32% | merge | `1023513D` (5), `910604N` (5), `1341721G` (4), `1085754L` (2), `1023518D` (1), … +2 more |
| SOCIETE TOURISTIQUE EL-MOURADI | registre_commerce | 7 | 30% | merge | `B2591996` (33), `B0936852004` (31), `B0945782008` (21), `B154762003` (12), `B110596199` (8), … +2 more |
| SOCIETE TUNISIAN MINING SERVICES TMS | matricule_fiscal | 7 | 32% | merge | `885534V` (9), `1031655P` (8), `1117724G` (3), `1090453J` (2), `1385234K` (2), … +2 more |
| SOCIETE ¨PALM | registre_commerce | 7 | 25% | merge | `B0963032008` (5), `B169581996` (4), `B2230432009` (4), `B1989952008` (3), `B1914712009` (2), … +2 more |
| SOGES | matricule_fiscal | 7 | 42% | merge | `434386T` (8), `513611Z` (3), `846879B` (3), `1597899A` (2), `1247170R` (1), … +2 more |
| SOGES | registre_commerce | 7 | 41% | merge | `B150112001` (11), `B1582001` (4), `B8170232010` (4), `B125032001` (3), `B139622003` (3), … +2 more |
| STPH | matricule_fiscal | 7 | 37% | merge | `620545F` (13), `1333416D` (6), `1334455Q` (6), `1113345G` (4), `620861Q` (3), … +2 more |
| STPH | registre_commerce | 7 | 47% | merge | `B1682001` (8), `B160351999` (3), `101636272009` (2), `1631411998` (1), `B061136272009` (1), … +2 more |
| TELECONTROL DETECTION SYSTEM TDS | matricule_fiscal | 7 | 48% | merge | `1054860R` (12), `635747R` (5), `1248870T` (2), `1485084W` (2), `1494683Q` (2), … +2 more |
| TUNISIE TRAVAUX | registre_commerce | 7 | 27% | merge | `B136082000` (4), `B0910232005` (3), `B131362003` (3), `B02234742016` (2), `B0151532007` (1), … +2 more |
| AGENCE METROPOLITAINE DE COMMUNICATION AMC | matricule_fiscal | 6 | 27% | merge | `1121499X` (3), `11338901P` (2), `1426882R` (2), `1565735E` (2), `1125531W` (1), … +1 more |
| AGHIR | matricule_fiscal | 6 | 27% | merge | `10315Y` (3), `1034536W` (2), `118470L` (2), `24758W` (2), `1184760L` (1), … +1 more |
| AL MAJD | matricule_fiscal | 6 | 31% | merge | `1255833F` (4), `853401G` (3), `1224618E` (2), `1587776J` (2), `1334051Y` (1), … +1 more |
| ALMAS | matricule_fiscal | 6 | 38% | merge | `755592H` (12), `644590P` (8), `1576701D` (5), `1327943K` (3), `15729441E` (2), … +1 more |
| AMILCAR PETROLEUM OPERATIONS | matricule_fiscal | 6 | 50% | merge | `1354717E` (8), `1183416S` (2), `1302718V` (2), `1375994Q` (2), `1120798B` (1), … +1 more |
| ARAMYS | registre_commerce | 6 | 36% | merge | `B248922006` (8), `B110098199` (6), `B05117292010` (3), `B117732002` (3), `110098199` (1), … +1 more |
| BATIMENT + | matricule_fiscal | 6 | 22% | merge | `1366650R` (4), `1398878L` (4), `30278X` (4), `1445022J` (3), `1127998N` (2), … +1 more |
| BATIMENT ET TRAVAUX PUBLICS | registre_commerce | 6 | 44% | merge | `B112692001` (8), `B08135012012` (4), `B2519442` (2), `B25194422009` (2), `B02246852018` (1), … +1 more |
| CHIC | registre_commerce | 6 | 33% | merge | `B0150892004` (5), `B0147982008` (3), `B034022009` (2), `B05134752009` (2), `B162611996` (2), … +1 more |
| CIE TUNISIENNE DES SACS CTS | matricule_fiscal | 6 | 31% | merge | `1116277A` (5), `614715S` (5), `1048950E` (3), `1165104B` (1), `835554X` (1), … +1 more |
| COBRA | matricule_fiscal | 6 | 39% | merge | `1007609S` (9), `1381615C` (5), `1260040M` (3), `914776B` (3), `1219583C` (2), … +1 more |
| COGEM + | registre_commerce | 6 | 76% | merge | `B157671997` (27), `B157651997` (4), `B811522013` (4), `B167651997` (3), `B02118972014` (2), … +1 more |
| COMPETENCES+ | registre_commerce | 6 | 36% | merge | `B2467052006` (4), `B2514712010` (3), `B01154632013` (1), `B02213552011` (1), `B02214472011` (1), … +1 more |
| CREATIVE TUNISIA | matricule_fiscal | 6 | 36% | merge | `918461B` (5), `1136604F` (2), `1252790Z` (2), `1431614F` (2), `1574971R` (2), … +1 more |
| DISTRIBUTION INFINITY PRODUCTS DIP | matricule_fiscal | 6 | 31% | merge | `1415621L` (5), `1388277K` (3), `1567012H` (3), `1450548V` (2), `1550101X` (2), … +1 more |
| EL ALIA | registre_commerce | 6 | 31% | merge | `B04216532011` (5), `B04148192013` (3), `B137892001` (3), `B04162562014` (2), `B04167522016` (2), … +1 more |
| ETABLISSEMENT ABDELMOULA | registre_commerce | 6 | 44% | merge | `B114121` (4), `B0158391996` (1), `B1110701997` (1), `B1141211997` (1), `B158391996` (1), … +1 more |
| ETABLISSEMENT GHORBEL | registre_commerce | 6 | 30% | merge | `B086852008` (3), `130362001` (2), `B189411999` (2), `B08242532012` (1), `B1161781997` (1), … +1 more |
| FLORENCE | registre_commerce | 6 | 33% | merge | `B0217292007` (5), `0765812006` (3), `B0248492006` (3), `05688880482` (2), `B0765812006` (1), … +1 more |
| GENERALE CONFECTION | matricule_fiscal | 6 | 33% | merge | `1277324P` (2), `1277624P` (2), `1343530K` (2), `1566746M` (2), `635708J` (2), … +1 more |
| HENKEL ALKI | registre_commerce | 6 | 26% | merge | `B0115402009` (11), `B17691996` (8), `17691996` (7), `B0132772009` (7), `B138881996` (7), … +1 more |
| HOPE | matricule_fiscal | 6 | 20% | merge | `1307384P` (2), `1477262Z` (2), `1510085T` (2), `1535596W` (2), `1445290D` (1), … +1 more |
| INGENIUM SA | matricule_fiscal | 6 | 40% | merge | `1351396V` (8), `1228097T` (4), `1349785J` (2), `1465661X` (2), `1472648S` (2), … +1 more |
| JADE | matricule_fiscal | 6 | 35% | merge | `1573640V` (7), `1068213M` (3), `1286660Y` (3), `1367255N` (3), `1602265F` (2), … +1 more |
| KENZA CONFECTION | matricule_fiscal | 6 | 20% | merge | `1163803P` (2), `1184411R` (2), `1310891E` (2), `31101A` (2), `1024565W` (1), … +1 more |
| LA ROSA | registre_commerce | 6 | 36% | merge | `B157982002` (4), `B01187332016` (2), `B2724692004` (2), `B0230572013` (1), `B08132072015` (1), … +1 more |
| LE FORUM | matricule_fiscal | 6 | 47% | merge | `341542Y` (9), `496235V` (4), `1227089P` (2), `1439183N` (2), `1543846R` (1), … +1 more |
| LE GOURMET | matricule_fiscal | 6 | 47% | merge | `382837M` (8), `1246908G` (2), `1340989F` (2), `1361892M` (2), `1581718X` (2), … +1 more |
| LE PILOTE | registre_commerce | 6 | 36% | merge | `B148161996` (5), `0840482006` (2), `B013562007` (2), `B1107051996` (2), `B2279322011` (2), … +1 more |
| LE PROFILE ALUMINIUM | registre_commerce | 6 | 42% | merge | `B2414532005` (14), `B1060332016` (9), `B1112491996` (8), `B1414531005` (3), `B15159552015` (1), … +1 more |
| LES GRANDES CARRIERES DU SAHEL GCS | matricule_fiscal | 6 | 25% | merge | `1124455X` (4), `1297035M` (4), `1276912T` (2), `1349265N` (2), `1443479G` (2), … +1 more |
| LOGISTIC SERVICES | matricule_fiscal | 6 | 27% | merge | `1330632X` (4), `1247537D` (3), `1174590F` (2), `1551008F` (2), `1556952L` (2), … +1 more |
| MAGASIN GENERAL | matricule_fiscal | 6 | 55% | merge | `32792V` (17), `33128W` (6), `1480261Y` (2), `1522968L` (2), `1578030V` (2), … +1 more |
| MAGHREB INTERNATIONAL PUBLICITE MIP | matricule_fiscal | 6 | 47% | merge | `867795N` (22), `826555X` (17), `1085799A` (4), `1393140B` (2), `1044729J` (1), … +1 more |
| MARHABA | registre_commerce | 6 | 38% | merge | `B111637199` (8), `B110832199` (4), `B110832` (3), `B1531998` (3), `B119911997` (2), … +1 more |
| NESRINE | registre_commerce | 6 | 25% | merge | `B0646752004` (2), `B126062000` (2), `B03149412014` (1), `B0719722006` (1), `B127932002` (1), … +1 more |
| NEXT PLUS | matricule_fiscal | 6 | 58% | merge | `1179641W` (7), `1179647W` (4), `1030293D` (2), `1173653Z` (2), `1354722B` (2), … +1 more |
| PANORAMA | registre_commerce | 6 | 56% | merge | `B17741996` (13), `B110311199` (5), `B1125262017` (2), `B112482000` (1), `B154402001` (1), … +1 more |
| PHENIX | registre_commerce | 6 | 43% | merge | `B0631872004` (9), `B2931995` (6), `B0313032008` (2), `B2427222005` (2), `B131002003` (1), … +1 more |
| POULINA | matricule_fiscal | 6 | 32% | merge | `1025115B` (6), `1013461D` (5), `2970D` (4), `29700D` (2), `2970Q` (1), … +1 more |
| PRIME SERVICES INFORMATIQUES | matricule_fiscal | 6 | 29% | merge | `846012E` (5), `1037704G` (4), `1105329K` (2), `1418949X` (2), `1451753C` (2), … +1 more |
| PROLOGIC HOLDING | matricule_fiscal | 6 | 38% | merge | `544435X` (29), `1219330G` (19), `644572M` (14), `1219836G` (5), `1389601F` (5), … +1 more |
| PYRAMIDE DE COMMERCE ET DE DISTRIBUTION | matricule_fiscal | 6 | 33% | merge | `1372631B` (4), `1156199A` (2), `1326996V` (2), `1554391Q` (2), `1218321B` (1), … +1 more |
| RAYEN | matricule_fiscal | 6 | 17% | merge | `1232090Q` (2), `1435731C` (2), `1487313Y` (2), `1517829R` (2), `1542141J` (2), … +1 more |
| SIAM | matricule_fiscal | 6 | 23% | merge | `1290393C` (3), `982529R` (3), `1419678X` (2), `1443611R` (2), `968167A` (2), … +1 more |
| SOCIETE AMIR DE COMMERCE | matricule_fiscal | 6 | 25% | merge | `1468828Q` (3), `1534952R` (3), `1526823L` (2), `1547201A` (2), `1425019D` (1), … +1 more |
| SOCIETE ANONYME IMMOBILIERE DU NORD DE LA TUNISIE | matricule_fiscal | 6 | 59% | merge | `6175A` (10), `510814W` (2), `539731T` (2), `4959441P` (1), `496236W` (1), … +1 more |
| SOCIETE BS DIAGNOSTICS | matricule_fiscal | 6 | 35% | merge | `1554065D` (7), `1203042V` (4), `642728F` (4), `1121428F` (2), `1512196J` (2), … +1 more |
| SOCIETE DE CONFECTION PRINTEMPS SPRING | registre_commerce | 6 | 25% | merge | `2516512007` (3), `B08219462015` (3), `B5171112017` (3), `B133892003` (1), `B2516512007` (1), … +1 more |
| SOCIETE DE CONGELATION DE PRODUITS DE MER CHAARI ET FILS LA REINE DES MERS | matricule_fiscal | 6 | 25% | merge | `635469N` (3), `996063A` (3), `1281515S` (2), `1483927G` (2), `1026050F` (1), … +1 more |
| SOCIETE EL-MAJD | registre_commerce | 6 | 22% | merge | `B1114241997` (2), `B151422003` (2), `B2210022007` (2), `A2218312009` (1), `B2287302010` (1), … +1 more |
| SOCIETE FAIZA | matricule_fiscal | 6 | 17% | merge | `1423977K` (2), `381507R` (2), `454938Q` (2), `908422N` (2), `916404H` (2), … +1 more |
| SOCIETE HAIFA | registre_commerce | 6 | 36% | merge | `B134542002` (13), `B2414932004` (8), `B198252010` (6), `B2453392005` (6), `B2489432008` (2), … +1 more |
| SOCIETE HAMZA | registre_commerce | 6 | 31% | merge | `B152682002` (4), `B25117372012` (3), `B0366752010` (2), `B15168152016` (2), `A91251092018` (1), … +1 more |
| SOCIETE HASNA | registre_commerce | 6 | 21% | merge | `B0130532006` (4), `B033342006` (4), `B126852001` (4), `B2439902009` (4), `B2132102013` (2), … +1 more |
| SOCIETE IDEAL SERVICE | matricule_fiscal | 6 | 32% | merge | `382095X` (6), `1538563Z` (4), `1020508T` (3), `1077576P` (2), `1361343L` (2), … +1 more |
| SOCIETE INTERACTIVE | registre_commerce | 6 | 32% | merge | `B0314032005` (6), `B012292007` (4), `0122912214` (3), `B1108451997` (2), `B139312003` (2), … +1 more |
| SOCIETE LE RECOUVREMENT | registre_commerce | 6 | 26% | merge | `B126472002` (10), `B155112002` (8), `B159212002` (8), `B138512002` (7), `B01154172009` (4), … +1 more |
| SOCIETE MAGHREBINE DES PRODUITS CERAMIQUES SMPC | registre_commerce | 6 | 55% | merge | `B620919971` (12), `B16209` (3), `B162091997` (3), `60744612007` (2), `024021` (1), … +1 more |
| SOCIETE MARWA DE COMMERCE | matricule_fiscal | 6 | 27% | merge | `1313122F` (4), `296604F` (4), `1264986Z` (2), `1458328T` (2), `1506444S` (2), … +1 more |
| SOCIETE NARJES | registre_commerce | 6 | 38% | merge | `B157181998` (2), `B158362002` (2), `B16088` (1), `B160881996` (1), `D1583998` (1), … +1 more |
| SOCIETE SAHA | matricule_fiscal | 6 | 27% | merge | `1263991R` (4), `1543653J` (3), `1031968F` (2), `1288850L` (2), `1319810A` (2), … +1 more |
| SOCIETE SALMA | registre_commerce | 6 | 22% | merge | `B01105882015` (2), `B01198202015` (2), `B0590082008` (2), `B08108012017` (1), `B2428312006` (1), … +1 more |
| SOCIETE SOUAD | matricule_fiscal | 6 | 20% | merge | `1491816X` (3), `505682T` (3), `859416Q` (3), `1564749G` (2), `1569233D` (2), … +1 more |
| SOCIETE TOURISTIQUE | registre_commerce | 6 | 60% | merge | `B110781199` (12), `B150761997` (3), `B116262001` (2), `B0116062016` (1), `B10781199` (1), … +1 more |
| SOMACO | matricule_fiscal | 6 | 46% | merge | `984133H` (10), `20047C` (4), `1211964C` (2), `1241649K` (2), `1377812B` (2), … +1 more |
| SOPRA | matricule_fiscal | 6 | 52% | merge | `960142F` (11), `545772R` (5), `639495H` (3), `1313643C` (2), `9609142F` (1), … +1 more |
| STEG ENERGIES RENOUVELABLES STEG ER | matricule_fiscal | 6 | 33% | merge | `996151Z` (4), `1206641B` (2), `1231993T` (2), `1295958Q` (2), `1307823R` (1), … +1 more |
| TAIBA | matricule_fiscal | 6 | 33% | merge | `1150389D` (4), `1404909Q` (3), `1485156V` (2), `1186194L` (1), `1258183G` (1), … +1 more |
| TRACE | matricule_fiscal | 6 | 27% | merge | `1175380B` (3), `1335287X` (2), `1489996X` (2), `1551467F` (2), `1198992Z` (1), … +1 more |

_4080 further conflicts are in `org_identifiers.csv`, where `is_conflicting = 1`._
