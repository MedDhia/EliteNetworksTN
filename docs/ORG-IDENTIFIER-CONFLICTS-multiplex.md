# Organisation identifier conflicts

Generated 2026-09-12 by `make orgattrs`.

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
| matricule_fiscal | 2805 of 7513 carrying one (37%) |
| registre_commerce | 1443 of 4762 carrying one (30%) |

Of 4248 conflicts, **3638 read as merges** and 610 as OCR damage.

The distribution is not what a metadata problem looks like. The worst node, **LA CONSULTING**, carries **1606 distinct matricule fiscal values** over 3739 observations, with its modal value accounting for only 0% of them. That is not one registration misread; it is a generic name fragment that every firm beginning with those words resolves onto.

**So the dominant failure in organisation resolution is the generic-name merge, not fuzzy-match noise.** A node like that does not degrade a variable — it fabricates a hub, and any centrality computed over it is meaningless. Treat the merge rows below as a blocklist: exclude those nodes, or split them, before using organisation-level structure.

Classifying these on the distance between the two closest values was the first attempt and it inverted the signal: among hundreds of numbers some pair is always one character apart, so the worst merges were labelled OCR. The test is instead whether the values cluster around the modal one.

## Conflicts, worst merges first

| organisation | identifier | values | modal share | reads as | most-observed values |
| --- | --- | --- | --- | --- | --- |
| LA CONSULTING | matricule_fiscal | 1606 | 0% | merge | `761845Y` (15), `993206J` (15), `1045760M` (13), `1194793B` (12), `1086710C` (11), … +1601 more |
| SOCIETE GENERALE | matricule_fiscal | 647 | 1% | merge | `1441813R` (17), `1009170Q` (15), `539187R` (15), `614671Y` (15), `868250M` (14), … +642 more |
| BATIMENT + | matricule_fiscal | 635 | 1% | merge | `992233H` (17), `42888H` (14), `934991S` (14), `974426N` (12), `1351489Z` (10), … +630 more |
| SA CONFECTION | matricule_fiscal | 532 | 1% | merge | `969630G` (20), `1068488P` (16), `623108A` (13), `1151391B` (12), `28703X` (12), … +527 more |
| GM DISTRIBUTION | matricule_fiscal | 500 | 1% | merge | `942468Z` (16), `10755245N` (14), `961902C` (13), `1030966Y` (12), `1061369C` (11), … +495 more |
| SOCIETE LE CONSEIL | matricule_fiscal | 377 | 5% | merge | `503855N` (57), `5905G` (29), `1022914N` (26), `1055931T` (22), `245588W` (16), … +372 more |
| LA CONSULTING | registre_commerce | 318 | 2% | merge | `B2421992009` (13), `B24114492009` (11), `B01229492012` (8), `B01229502012` (8), `B01234272013` (8), … +313 more |
| AS DISTRIBUTION | matricule_fiscal | 301 | 2% | merge | `943751D` (17), `1058118J` (15), `505875B` (15), `1125286C` (14), `1050387V` (12), … +296 more |
| SOCIETE GENERALE | registre_commerce | 272 | 2% | merge | `B118591997` (20), `B1140791997` (16), `B2459652006` (16), `B0388692008` (14), `B1177522009` (12), … +267 more |
| DESIGN | matricule_fiscal | 254 | 4% | merge | `1028699C` (26), `1053081R` (14), `737651Z` (11), `1075262P` (8), `1261336F` (8), … +249 more |
| BEST | matricule_fiscal | 240 | 4% | merge | `103539B` (28), `1098673E` (12), `851938D` (12), `1385253N` (9), `1419832N` (9), … +235 more |
| SOCIETE NOUR | matricule_fiscal | 215 | 2% | merge | `986698B` (14), `1027384F` (12), `1255303H` (10), `620582L` (10), `1153975E` (9), … +210 more |
| V PRODUCTION | matricule_fiscal | 209 | 5% | merge | `804219N` (26), `784074H` (11), `1062872S` (8), `3000N` (8), `1009060K` (7), … +204 more |
| SOCIETE TOURISTIQUE | matricule_fiscal | 206 | 2% | merge | `341715B` (17), `389148Y` (16), `40782P` (13), `1091895M` (12), `10973D` (12), … +201 more |
| R INDUSTRIE | matricule_fiscal | 196 | 3% | merge | `220007C` (14), `445129M` (13), `381721W` (12), `1026883R` (10), `962324T` (10), … +191 more |
| Y SOLUTIONS | matricule_fiscal | 194 | 2% | merge | `1377242N` (8), `539876L` (8), `1145993K` (5), `1202048X` (5), `1226482Q` (5), … +189 more |
| SA CONFECTION | registre_commerce | 191 | 4% | merge | `B1114371996` (20), `1111931996` (16), `B150892002` (12), `B131051999` (10), `B15176842010` (8), … +186 more |
| SOCIETE TOURISTIQUE | registre_commerce | 188 | 5% | merge | `B0936852004` (33), `B180221997` (23), `B147961997` (22), `B197141996` (18), `B110781199` (15), … +183 more |
| UB ENGINEERING | matricule_fiscal | 176 | 2% | merge | `1161351Y` (9), `1130357J` (8), `11333251N` (7), `1290623X` (7), `871525W` (7), … +171 more |
| GM DISTRIBUTION | registre_commerce | 165 | 4% | merge | `B0154512012` (20), `B1163071997` (12), `B160462000` (12), `B183411996` (12), `B1681997` (10), … +160 more |
| CONCEPT | matricule_fiscal | 163 | 3% | merge | `1045318X` (13), `1063172Z` (12), `1030163T` (10), `747035K` (8), `1371819H` (7), … +158 more |
| SOCIETE ONS DE TRAVAUX PUBLICS | matricule_fiscal | 160 | 3% | merge | `620694T` (12), `1450454P` (9), `1393510H` (8), `827397F` (7), `980466K` (7), … +155 more |
| DECO | matricule_fiscal | 157 | 5% | merge | `913236X` (20), `1076287D` (19), `1193140N` (10), `1424659C` (7), `1193237X` (6), … +152 more |
| SOCIETE M | matricule_fiscal | 154 | 2% | merge | `1293190F` (8), `1214095T` (7), `992132D` (7), `1387182Z` (6), `1194059B` (5), … +149 more |
| BM INTERNATIONAL TRADING | matricule_fiscal | 150 | 3% | merge | `1390293F` (10), `1099614X` (8), `13448286P` (8), `1189215L` (6), `1437753S` (6), … +145 more |
| BATIMENT + | registre_commerce | 146 | 4% | merge | `B2445732005` (14), `A0559062006` (12), `B177791996` (7), `B2469892011` (7), `B26166382013` (7), … +141 more |
| SOCIETE DE MATERIAUX DE CONSTRUCTION SMC | matricule_fiscal | 140 | 4% | merge | `320570M` (14), `981726Q` (13), `1062286E` (12), `939553V` (10), `1219833B` (8), … +135 more |
| SOCIETE EL-BARAKA | matricule_fiscal | 134 | 6% | merge | `708583S` (19), `827657G` (10), `964532J` (9), `908322K` (8), `349694Z` (7), … +129 more |
| SOCIETE LE CONSEIL | registre_commerce | 134 | 4% | merge | `D081862008` (22), `B1135031997` (19), `B138811996` (17), `B0123702007` (15), `B130221998` (15), … +129 more |
| DELTA | matricule_fiscal | 128 | 3% | merge | `779069W` (12), `794378W` (10), `1083337N` (8), `1153341Z` (8), `1180006P` (8), … +123 more |
| SOCIETE LE METAL | matricule_fiscal | 126 | 2% | merge | `601807C` (7), `718879M` (7), `1079342F` (6), `17565W` (6), `967804C` (6), … +121 more |
| SOCIETE DE PROMOTION IMMOBILIERE | matricule_fiscal | 119 | 9% | merge | `754848J` (32), `719356S` (18), `570983W` (16), `833596Z` (12), `437566J` (11), … +114 more |
| SOCIETE IS TECHNOLOGIE | matricule_fiscal | 111 | 4% | merge | `1071410Q` (9), `745486B` (7), `1015298V` (5), `1356120N` (5), `1402737E` (5), … +106 more |
| SOCIETE DE PROMOTION IMMOBILIERE | registre_commerce | 105 | 6% | merge | `B110002001` (21), `B151252000` (14), `B1117961997` (12), `B1147261997` (10), `B149702000` (9), … +100 more |
| 2M INFORMATIQUE | matricule_fiscal | 100 | 4% | merge | `1067564E` (10), `1070998D` (9), `24485P` (7), `1032633M` (6), `1046173C` (6), … +95 more |
| GLOBAL SERVICES | matricule_fiscal | 97 | 5% | merge | `926133J` (11), `1211478S` (5), `1226630J` (5), `1242378K` (5), `1186036X` (4), … +92 more |
| LE CONFORT | matricule_fiscal | 96 | 4% | merge | `1142832E` (9), `983192Q` (8), `924957K` (7), `1349517P` (6), `1062378H` (5), … +91 more |
| SOLUTION T | matricule_fiscal | 93 | 4% | merge | `1075110Y` (8), `1179895S` (6), `1338269H` (6), `1434623V` (6), `1210274C` (5), … +88 more |
| SOCIETE TRAVAUX ET SERVICES | matricule_fiscal | 90 | 7% | merge | `943168T` (16), `921771N` (10), `1043101X` (8), `1175186B` (7), `1328631A` (7), … +85 more |
| R INDUSTRIE | registre_commerce | 88 | 5% | merge | `B152541998` (15), `B2425942007` (14), `B15203632010` (13), `B13952002` (12), `B138841997` (8), … +83 more |
| AS DISTRIBUTION | registre_commerce | 84 | 6% | merge | `B0149222008` (15), `B0321942004` (15), `B2422011` (10), `B039222009` (8), `B03181762010` (7), … +79 more |
| LA RESIDENCE | matricule_fiscal | 83 | 6% | merge | `36022Z` (17), `17216B` (13), `1461981T` (10), `1269034D` (9), `20074F` (9), … +78 more |
| SOCIETE YASMINE | matricule_fiscal | 83 | 6% | merge | `588259N` (10), `539563W` (7), `960267T` (7), `1259329L` (6), `1280926E` (6), … +78 more |
| SOCIETE DE SERVICES DE TUNISIE | matricule_fiscal | 81 | 7% | merge | `917973S` (16), `1063373G` (14), `1285193M` (7), `1127501Y` (6), `1328394G` (6), … +76 more |
| V PRODUCTION | registre_commerce | 79 | 5% | merge | `B08170952013` (12), `B141032002` (11), `B1577582007` (8), `B2471642008` (8), `B1126011997` (7), … +74 more |
| STEG INTERNATIONAL SERVICES | matricule_fiscal | 78 | 6% | merge | `1319461Z` (16), `830641Y` (12), `1031244Y` (10), `1473178M` (9), `1125346X` (8), … +73 more |
| SOCIETE LE CLUB | matricule_fiscal | 77 | 7% | merge | `761810L` (16), `967482E` (8), `1175993B` (7), `633884R` (7), `910774G` (7), … +72 more |
| SOCIETE NOUR | registre_commerce | 76 | 4% | merge | `B2478702007` (9), `B25126702012` (8), `B150052001` (7), `B27103612010` (7), `B51118782013` (6), … +71 more |
| N TRAINING | matricule_fiscal | 75 | 3% | merge | `1060511K` (5), `1419069B` (5), `1304313K` (4), `561264T` (4), `1041840T` (3), … +70 more |
| LE SANITAIRE | matricule_fiscal | 74 | 7% | merge | `382465D` (19), `1310922T` (17), `1188187W` (14), `635649Q` (14), `740351P` (13), … +69 more |
| SMAG | matricule_fiscal | 72 | 7% | merge | `953145R` (9), `1143469K` (5), `1211768A` (3), `1242010D` (3), `1439003S` (3), … +67 more |
| SOFTWARE SA | matricule_fiscal | 71 | 6% | merge | `1236582Z` (12), `1085475G` (8), `1266489V` (7), `1044093V` (6), `1312792L` (6), … +66 more |
| BEST | registre_commerce | 70 | 6% | merge | `B2435342009` (10), `B0243322005` (8), `B151832003` (7), `B24148832011` (6), `B113462003` (5), … +65 more |
| SOCIETE DE CONSULTING ET DE SERVICES | matricule_fiscal | 70 | 3% | merge | `1251944V` (4), `1413097E` (4), `1023641L` (3), `1201450Z` (3), `1225279K` (3), … +65 more |
| ARC EN CIEL | matricule_fiscal | 61 | 6% | merge | `1357169L` (7), `775642L` (7), `1244934A` (6), `1112658S` (5), `1065233D` (4), … +56 more |
| BB | matricule_fiscal | 61 | 5% | merge | `958835J` (6), `1161062R` (3), `975694M` (3), `1084410J` (2), `1139737G` (2), … +56 more |
| SOCIETE CONTACT | matricule_fiscal | 60 | 9% | merge | `1408057M` (17), `613851W` (13), `926008E` (13), `1047041V` (10), `47218V` (8), … +55 more |
| GS COMPANY INTERNATIONAL | matricule_fiscal | 59 | 6% | merge | `1451853F` (8), `1426076S` (6), `1072718N` (3), `1135723H` (3), `1172581W` (3), … +54 more |
| SOCIETE ESSADAKA DE BATIMENTS ET DE TRAVAUX PUBLIQUES EN ETAT DE LIQUIDATION | matricule_fiscal | 59 | 13% | merge | `3783G` (18), `1328549H` (9), `1326750Y` (8), `1052401H` (5), `1075771G` (4), … +54 more |
| BATIMENT ET TRAVAUX PUBLICS | matricule_fiscal | 58 | 13% | merge | `953342V` (21), `1414945A` (9), `566198Y` (7), `1155454R` (6), `1544079E` (6), … +53 more |
| DESIGN | registre_commerce | 57 | 7% | merge | `B116372002` (11), `B24155782012` (8), `B0387272008` (6), `B2552512012` (6), `B0124622008` (5), … +52 more |
| AB CORPORATION | matricule_fiscal | 56 | 16% | merge | `1031794A` (25), `970037L` (9), `1027497P` (6), `1341094C` (5), `760581N` (5), … +51 more |
| AUTO PIECES | matricule_fiscal | 54 | 4% | merge | `1376937K` (5), `1172428M` (4), `1461492F` (4), `1604770C` (4), `790579L` (4), … +49 more |
| SOCIETE DE PRODUITS ALIMENTAIRES SPA | matricule_fiscal | 54 | 5% | merge | `620700Y` (6), `988334H` (6), `1459101E` (5), `1269783L` (4), `1037019R` (3), … +49 more |
| OASIS | matricule_fiscal | 53 | 12% | merge | `1064105R` (20), `885095S` (13), `1315534G` (10), `1174346V` (9), `1489912A` (7), … +48 more |
| SOCIETE ESSADAKA DE BATIMENTS ET DE TRAVAUX PUBLIQUES EN ETAT DE LIQUIDATION | registre_commerce | 52 | 20% | merge | `B147451996` (31), `B110141996` (8), `B1101501997` (8), `B01229652013` (6), `B2536192008` (5), … +47 more |
| UB ENGINEERING | registre_commerce | 52 | 10% | merge | `B2416272004` (13), `B1855902005` (7), `B2410882007` (7), `A0281862005` (6), `B0358942013` (5), … +47 more |
| Z PRODUCTION | matricule_fiscal | 52 | 7% | merge | `1030990Y` (11), `1320454R` (10), `579934A` (9), `940993H` (9), `842838Z` (7), … +47 more |
| SOCIETE GENERALE TRAVAUX | matricule_fiscal | 51 | 5% | merge | `1245624S` (7), `960966Q` (6), `1247675N` (5), `1567658S` (5), `1118876C` (4), … +46 more |
| ENTREPRISE EL-AMEN | matricule_fiscal | 50 | 10% | merge | `718584Z` (18), `1176119T` (15), `973190H` (12), `633754G` (11), `513415X` (10), … +45 more |
| SOCIETE LE METAL | registre_commerce | 50 | 9% | merge | `B2748222004` (10), `B168032000` (6), `B117621999` (5), `B181212000` (5), `B08214662012` (4), … +45 more |
| CONCEPT | registre_commerce | 49 | 10% | merge | `A0266122006` (13), `A0172742005` (7), `B02133132009` (7), `B02206862014` (7), `B019102013` (6), … +44 more |
| SOCIETE EL-BARAKA | registre_commerce | 49 | 8% | merge | `B111232003` (10), `B07114662009` (9), `B140282003` (8), `B163411996` (7), `B2434482007` (5), … +44 more |
| SOCIETE TROIS | matricule_fiscal | 49 | 8% | merge | `1109574P` (10), `1350285J` (9), `874678B` (7), `1158668S` (6), `1257666S` (6), … +44 more |
| MANUFACTURE | matricule_fiscal | 47 | 7% | merge | `45372W` (8), `1321919J` (5), `1492491A` (5), `2961C` (5), `847871X` (5), … +42 more |
| SOCIETE DE MATERIAUX DE CONSTRUCTION SMC | registre_commerce | 46 | 9% | merge | `B2450432005` (12), `A2675872005` (10), `B1105061997` (6), `A0821942005` (5), `B150501996` (5), … +41 more |
| SOCIETE LIFE | matricule_fiscal | 46 | 24% | merge | `578800G` (34), `1504731N` (6), `1487549S` (5), `926524W` (5), `1119027W` (4), … +41 more |
| FARAH | matricule_fiscal | 43 | 10% | merge | `38228W` (10), `808998V` (5), `843718W` (5), `930752L` (4), `1108075V` (3), … +38 more |
| RAYEN | matricule_fiscal | 43 | 4% | merge | `1217172C` (4), `1288532Z` (3), `1365752S` (3), `1488987R` (3), `1519342F` (3), … +38 more |
| IT DEVELOPMENT | matricule_fiscal | 42 | 5% | merge | `1022492E` (4), `1206230K` (3), `1236884L` (3), `1265868Y` (3), `978911P` (3), … +37 more |
| LE CONFORT | registre_commerce | 42 | 11% | merge | `B139842001` (12), `B121832000` (9), `A0233582007` (7), `B131442003` (6), `B2457792010` (5), … +37 more |
| LM INFORMATIQUE | matricule_fiscal | 42 | 5% | merge | `1023991G` (5), `1275568T` (4), `1412315Q` (4), `539645X` (4), `1041287Q` (3), … +37 more |
| SOCIETE LINA | matricule_fiscal | 42 | 6% | merge | `1477399R` (5), `1120674P` (4), `1134770L` (4), `969927X` (3), `994398N` (3), … +37 more |
| SOCIETE AMEL | matricule_fiscal | 40 | 14% | merge | `1005164A` (15), `315719G` (7), `11172F` (6), `44862F` (6), `884116A` (4), … +35 more |
| BM INTERNATIONAL TRADING | registre_commerce | 39 | 7% | merge | `B2436882009` (8), `B25107542009` (7), `B0118922014` (5), `B0268932007` (5), `B09162822013` (5), … +34 more |
| ELITE + | matricule_fiscal | 39 | 7% | merge | `1415101Q` (5), `1452898Z` (3), `1836128T` (3), `1160652E` (2), `1224291B` (2), … +34 more |
| PRESTIGE | matricule_fiscal | 39 | 11% | merge | `1014573Q` (10), `1025936H` (7), `1198362Y` (5), `1286812W` (4), `340668H` (4), … +34 more |
| SOCIETE ONS DE TRAVAUX PUBLICS | registre_commerce | 39 | 11% | merge | `B0210922004` (14), `B111081999` (12), `B138161996` (9), `B0172452016` (7), `B0162942016` (5), … +34 more |
| AMANA | matricule_fiscal | 38 | 6% | merge | `1437026R` (6), `1082302X` (5), `504321Q` (5), `1208857A` (4), `10761959W` (3), … +33 more |
| AZUR | matricule_fiscal | 38 | 11% | merge | `1076765N` (11), `1088572V` (5), `1465044B` (5), `1383227C` (4), `745443P` (4), … +33 more |
| DELTA | registre_commerce | 38 | 10% | merge | `B245302009` (12), `B0129522005` (7), `B5142002014` (7), `B0419762012` (6), `B115761999` (6), … +33 more |
| SOCIETE BAYA | matricule_fiscal | 38 | 6% | merge | `1152664M` (5), `1270226B` (5), `1276556T` (3), `1366721P` (3), `1540683C` (3), … +33 more |
| SOCIETE BW TRADE COMPANY | matricule_fiscal | 38 | 12% | merge | `924654X` (11), `1476721B` (7), `1327135J` (4), `1443069R` (4), `1236523M` (3), … +33 more |
| SOCIETE EVENT | matricule_fiscal | 38 | 14% | merge | `816663R` (15), `795140D` (9), `1477001D` (6), `1481965E` (5), `1113398W` (4), … +33 more |
| SOCIETE GOLD | matricule_fiscal | 38 | 9% | merge | `1236162G` (8), `1014821M` (4), `1430009K` (4), `1481050S` (4), `995545K` (4), … +33 more |
| SOCIETE UNIQUE | matricule_fiscal | 38 | 24% | merge | `947693D` (26), `431699A` (7), `2309D` (6), `965502G` (4), `1074529T` (3), … +33 more |
| Y SOLUTIONS | registre_commerce | 37 | 8% | merge | `B0156442013` (8), `B51234562014` (8), `B187332007` (7), `B016112007` (5), `B0329332007` (5), … +32 more |
| LA RESIDENCE | registre_commerce | 36 | 15% | merge | `B182181999` (18), `B148441997` (9), `B152252000` (8), `B1941932017` (7), `B01224482015` (5), … +31 more |
| SOCIETE BLUE TRADE INTERNATIONAL | matricule_fiscal | 36 | 10% | merge | `1109651K` (9), `47958B` (6), `1032082C` (4), `1282823G` (4), `1125064P` (3), … +31 more |
| EL WAFA | matricule_fiscal | 35 | 8% | merge | `718579C` (6), `1385448Y` (4), `1042438A` (3), `382843K` (3), `945342Y` (3), … +30 more |
| SAAD | matricule_fiscal | 35 | 8% | merge | `779285C` (5), `1192202F` (4), `1195307C` (4), `1537449T` (4), `1435000X` (3), … +30 more |
| SOCIETE MEGA | matricule_fiscal | 35 | 8% | merge | `510712Q` (8), `455973Y` (7), `892021Q` (7), `1282605Y` (5), `1318657F` (4), … +30 more |
| LA PERLE | matricule_fiscal | 34 | 6% | merge | `1317734X` (5), `1525158W` (5), `1118961Y` (4), `1484773L` (4), `1085490F` (3), … +29 more |
| SERVICES INTERNATIONAL BSIR TOTALEMENT EXPORTATRICE SIB | matricule_fiscal | 34 | 14% | merge | `1033827A` (18), `886774P` (15), `1432766B` (11), `1130386P` (7), `1009827K` (6), … +29 more |
| SOCIETE ADEM | matricule_fiscal | 34 | 6% | merge | `1314988F` (5), `1240148N` (4), `1280773F` (4), `889656X` (4), `1319477H` (3), … +29 more |
| SOCIETE DES SERVICES INDUSTRIELS | matricule_fiscal | 34 | 7% | merge | `1053421R` (5), `1251036Q` (4), `1490438L` (3), `1507593K` (3), `453700P` (3), … +29 more |
| SOCIETE IS TECHNOLOGIE | registre_commerce | 34 | 6% | merge | `B23129462014` (5), `B2453162007` (5), `B175422000` (4), `B2442612005` (4), `B2457012003` (4), … +29 more |
| 2M INFORMATIQUE | registre_commerce | 33 | 12% | merge | `A0139312008` (9), `B03206812016` (4), `B12229732016` (4), `B125711997` (4), `B17671997` (4), … +28 more |
| MAC INTERNATIONAL | matricule_fiscal | 33 | 7% | merge | `703687D` (7), `986095D` (7), `962245W` (6), `434140X` (5), `1209640N` (4), … +28 more |
| SOCIETE INTERNATIONAL TRADING COMPANY | matricule_fiscal | 33 | 11% | merge | `1432918Z` (10), `1238613X` (7), `1006279Q` (6), `1242753N` (5), `31475E` (4), … +28 more |
| SOCIETE LE RECOUVREMENT | matricule_fiscal | 33 | 12% | merge | `1116832F` (13), `794031V` (10), `815441C` (8), `817264M` (8), `1285632P` (7), … +28 more |
| SOCIETE DES PIECES DE RECHANGE DU SUD | matricule_fiscal | 32 | 7% | merge | `1255772K` (5), `1007807X` (4), `1267447N` (3), `1312172M` (3), `1533246R` (3), … +27 more |
| SOCIETE JARDIN DEDEN CONDITIONNEMENT ET TRANSFORMATION DES DATTES | matricule_fiscal | 32 | 25% | merge | `633291W` (37), `1038250B` (12), `1136890C` (10), `1039394X` (9), `975739H` (8), … +27 more |
| MANUFACTURE | registre_commerce | 31 | 10% | merge | `B127461998` (10), `B11891998` (9), `B136451998` (7), `B14901998` (6), `B1127301997` (5), … +26 more |
| SOCIETE INES | matricule_fiscal | 31 | 12% | merge | `433713J` (10), `548462S` (9), `913925R` (5), `496362B` (4), `1117976B` (3), … +26 more |
| SOCIETE JAWHARA | matricule_fiscal | 31 | 12% | merge | `496428C` (10), `918740F` (8), `738541Y` (6), `1113076E` (5), `1238899C` (5), … +26 more |
| SOCIETE LE FRIGO | matricule_fiscal | 31 | 8% | merge | `1369897C` (6), `787646E` (5), `1002434Q` (4), `1068443A` (3), `109469X` (3), … +26 more |
| SPEED | matricule_fiscal | 31 | 11% | merge | `1489982Q` (8), `809748G` (6), `1135020G` (4), `1147532R` (3), `1470123H` (3), … +26 more |
| EL HANA | matricule_fiscal | 30 | 10% | merge | `385268N` (7), `601865N` (5), `1118917T` (4), `1125347Y` (4), `767542L` (4), … +25 more |
| LE SANITAIRE | registre_commerce | 30 | 14% | merge | `B1158171997` (18), `B81154182013` (15), `B0831882005` (11), `B151732000` (9), `B24153442009` (9), … +25 more |
| LINK | matricule_fiscal | 30 | 14% | merge | `1214663E` (14), `904223Q` (11), `1226388T` (7), `1029460J` (5), `1036969C` (5), … +25 more |
| SOCIETE DE MISE EN VALEUR ET DE DEVELOPPEMENT AGRICOLE | matricule_fiscal | 30 | 11% | merge | `587620F` (13), `736406H` (11), `1361054E` (10), `349464L` (9), `539810R` (8), … +25 more |
| SOCIETE E SOLUTIONS | matricule_fiscal | 30 | 6% | merge | `1504421B` (4), `737611Q` (4), `1097112V` (3), `1141632T` (3), `1253627S` (3), … +25 more |
| SOCIETE GENERALE TRAVAUX | registre_commerce | 30 | 11% | merge | `B146401996` (9), `B162921996` (7), `B278532004` (6), `B017942010` (4), `B134012003` (4), … +25 more |
| SOCIETE YASMINE | registre_commerce | 30 | 8% | merge | `B048822013` (6), `B2426542006` (5), `B5141432013` (5), `B0928882005` (4), `B140332002` (4), … +25 more |
| ARC EN CIEL | registre_commerce | 29 | 21% | merge | `B131681997` (12), `B2077192012` (6), `B1118861996` (3), `B2430602012` (3), `B0255312005` (2), … +24 more |
| AVENIR | matricule_fiscal | 29 | 11% | merge | `836646E` (7), `1424004R` (5), `1396139X` (4), `972461H` (4), `749193H` (3), … +24 more |
| CARTHAGO SA | matricule_fiscal | 29 | 16% | merge | `35760Z` (13), `757760P` (10), `579940Y` (5), `875861C` (5), `1016555X` (4), … +24 more |
| DECO | registre_commerce | 29 | 19% | merge | `B0716152005` (22), `A0283312008` (19), `B0158162011` (10), `B0714302018` (6), `B0119582010` (4), … +24 more |
| EMNA | matricule_fiscal | 29 | 13% | merge | `1104866C` (10), `983196V` (6), `418040A` (4), `956752Y` (4), `1135457J` (3), … +24 more |
| OGER INTERNATIONAL TUNISIE, OIT | matricule_fiscal | 29 | 15% | merge | `960142F` (10), `1197615W` (6), `1066850D` (3), `1156740Z` (3), `1179920A` (3), … +24 more |
| SOCIETE JARDIN DEDEN CONDITIONNEMENT ET TRANSFORMATION DES DATTES | registre_commerce | 29 | 15% | merge | `B141191997` (18), `B0122862007` (10), `B249482008` (10), `B2711432008` (10), `80352992006` (8), … +24 more |
| SOCIETE LE CLUB | registre_commerce | 29 | 12% | merge | `B0369552010` (13), `B152292003` (10), `B127172001` (7), `B0156192007` (6), `B12661998` (6), … +24 more |
| SOCIETE LE LABORATOIRE | matricule_fiscal | 29 | 16% | merge | `4156N` (13), `1303202Z` (7), `979646W` (7), `818915E` (5), `1186830R` (3), … +24 more |
| SOCIETE EL-WIFAK | matricule_fiscal | 28 | 8% | merge | `433134V` (4), `283777Q` (3), `4414611N` (3), `74526033N` (3), `1087708N` (2), … +23 more |
| SOCIETE IMEN | matricule_fiscal | 28 | 13% | merge | `1248862T` (11), `418182P` (9), `1046396R` (5), `475636T` (5), `1114188R` (4), … +23 more |
| SOCIETE ZAABI DES BATIMENTS ET TRAVAUX PUBLICS | matricule_fiscal | 28 | 10% | merge | `1215786V` (7), `735936B` (5), `1085161Q` (4), `873041N` (4), `1331844M` (3), … +23 more |
| STEG INTERNATIONAL SERVICES | registre_commerce | 28 | 16% | merge | `2616712013` (16), `B117762003` (15), `B01171042016` (6), `B0140512010` (6), `B115611997` (6), … +23 more |
| LE FUTURE | matricule_fiscal | 27 | 26% | merge | `1021337X` (22), `1323377J` (7), `1361978S` (4), `1052650Z` (3), `1195893J` (3), … +22 more |
| HM BUREAUTIQUE ET INFORMATIQUE | matricule_fiscal | 26 | 22% | merge | `1032255F` (15), `635721F` (10), `1092007Y` (2), `1135184C` (2), `1171308A` (2), … +21 more |
| HR CONNECT | matricule_fiscal | 26 | 11% | merge | `1062305P` (6), `1088686E` (3), `1030859W` (2), `1134165V` (2), `1180788G` (2), … +21 more |
| SOCIETE DE MISE EN VALEUR ET DE DEVELOPPEMENT AGRICOLE | registre_commerce | 26 | 20% | merge | `B2469412008` (16), `B131041997` (8), `B11291` (7), `B129711998` (6), `B191631999` (6), … +21 more |
| SOCIETE MULTISERVICES | matricule_fiscal | 26 | 9% | merge | `1024399A` (5), `1028994G` (4), `1604206C` (4), `1163408G` (3), `1435665K` (3), … +21 more |
| SOCIETE NEGOCE INTERNATIONAL | matricule_fiscal | 26 | 15% | merge | `822360V` (10), `1174521R` (4), `737643Z` (4), `1248875Z` (3), `1326259R` (3), … +21 more |
| EL MANAR | matricule_fiscal | 25 | 18% | merge | `578020K` (13), `30838H` (7), `326140T` (5), `874048A` (5), `1374242A` (3), … +20 more |
| SOCIETE AM DE SERVICE ET COMMERCE INTERNATIONALE NON RESIDENTE | matricule_fiscal | 25 | 16% | merge | `1092524Q` (14), `990612G` (14), `827532T` (8), `958863N` (7), `741392D` (5), … +20 more |
| SOCIETE EL-AMAL | matricule_fiscal | 25 | 21% | merge | `944132K` (15), `620899F` (7), `1264278B` (5), `1395085W` (5), `1416538X` (3), … +20 more |
| SOCIETE ENTREPRISE TRABELSI | matricule_fiscal | 25 | 15% | merge | `624954M` (9), `1294912W` (5), `625305M` (3), `1114831W` (2), `1130066A` (2), … +20 more |
| SOCIETE INTERNATIONAL CONSULTING SERVICES | matricule_fiscal | 25 | 9% | merge | `1277553V` (5), `1296669N` (4), `978213T` (4), `1042984P` (2), `1147560W` (2), … +20 more |
| SOCIETE MODERNE DE BATIMENT | matricule_fiscal | 25 | 20% | merge | `1298072X` (13), `1305051L` (4), `1420980R` (4), `840486L` (4), `725469P` (3), … +20 more |
| TUNISIE DISTRIBUTION | matricule_fiscal | 25 | 10% | merge | `803516Q` (8), `856180B` (7), `960004W` (7), `1277500F` (6), `432475K` (6), … +20 more |
| LE MOTEUR | matricule_fiscal | 24 | 13% | merge | `1130552K` (9), `1483726Z` (8), `836992W` (8), `1183353V` (5), `341584J` (4), … +19 more |
| MENUISERIE ALUMINIUM | matricule_fiscal | 24 | 14% | merge | `1578551R` (9), `1306432A` (6), `584166R` (5), `1162751Q` (4), `1139227N` (3), … +19 more |
| MODA | matricule_fiscal | 24 | 10% | merge | `1219980M` (6), `1003502P` (4), `1203618P` (4), `1309829G` (4), `993259Y` (4), … +19 more |
| OASIS | registre_commerce | 24 | 15% | merge | `B2259412008` (12), `B24204242010` (9), `B153031997` (8), `B0138512007` (6), `B122761998` (5), … +19 more |
| SOCIETE EL-YOSR | matricule_fiscal | 24 | 15% | merge | `1110053J` (9), `1307276L` (4), `1336448A` (4), `1091147F` (3), `1438695E` (3), … +19 more |
| SOCIETE ¨PALM | matricule_fiscal | 24 | 10% | merge | `1065132Z` (7), `1028282E` (6), `1573563Z` (6), `1574595M` (5), `1146870D` (4), … +19 more |
| SOCIETE DE COMMERCE INTERNATIONAL | matricule_fiscal | 23 | 12% | merge | `1226564R` (6), `1036844P` (4), `1262141A` (4), `1244922W` (3), `1478168G` (3), … +18 more |
| SOCIETE IRIS | matricule_fiscal | 23 | 7% | merge | `1059199G` (3), `1377953P` (3), `766923R` (3), `956958L` (3), `1086752N` (2), … +18 more |
| SOFTWARE SA | registre_commerce | 23 | 13% | merge | `B249122009` (8), `B24184662012` (5), `B01163002013` (3), `B01238752012` (3), `B1149167997` (3), … +18 more |
| TUNISIE TRAVAUX | matricule_fiscal | 23 | 8% | merge | `111269V` (5), `852544S` (5), `857921V` (5), `1419094C` (4), `1112692V` (3), … +18 more |
| Z PRODUCTION | registre_commerce | 23 | 17% | merge | `B02198832013` (13), `A0186322007` (11), `B133402003` (7), `B0330152006` (6), `B156472002` (6), … +18 more |
| EL WIFEK | matricule_fiscal | 22 | 12% | merge | `784622H` (6), `504352Y` (4), `1344233H` (3), `438610Z` (3), `1087338G` (2), … +17 more |
| GLOBAL SERVICES | registre_commerce | 22 | 12% | merge | `B0265952012` (6), `B24219112011` (5), `B01148272015` (4), `B02216192015` (4), `B11271998` (4), … +17 more |
| SOCIETE ALFA | matricule_fiscal | 22 | 5% | merge | `1064302V` (2), `1091356N` (2), `1107960M` (2), `1198681L` (2), `1214107E` (2), … +17 more |
| SOCIETE DE SERVICES DE TUNISIE | registre_commerce | 22 | 9% | merge | `B03164962016` (7), `B03165082016` (7), `B2627832013` (7), `B2422652005` (6), `B51240852013` (6), … +17 more |
| SOCIETE TRAVAUX ET SERVICES | registre_commerce | 22 | 21% | merge | `A0145822007` (16), `B123692000` (8), `B0359162003` (6), `B0216672006` (5), `B1557822012` (5), … +17 more |
| SOCIETE TROIS | registre_commerce | 22 | 12% | merge | `B0130252007` (7), `B2420262004` (7), `B24138612012` (6), `B51164092016` (5), `B0122862007` (3), … +17 more |
| LA ROSA | matricule_fiscal | 21 | 13% | merge | `1322794T` (6), `1543744L` (4), `1154Y` (2), `1201248Z` (2), `1218406F` (2), … +16 more |
| MAYA | matricule_fiscal | 21 | 10% | merge | `1031522B` (5), `1212195N` (4), `1327035F` (4), `1165010W` (3), `1222536V` (3), … +16 more |
| SICAV ENTREPRISE | registre_commerce | 21 | 17% | merge | `B186251996` (20), `B11574` (17), `B115741997` (16), `B014377` (11), `B1157641997` (9), … +16 more |
| SOCIETE LE COIN | matricule_fiscal | 21 | 28% | merge | `1231067M` (18), `1223649H` (4), `1386252R` (4), `795077P` (4), `1511509B` (3), … +16 more |
| SUD SERVICES | matricule_fiscal | 21 | 20% | merge | `513505Y` (10), `1237146L` (4), `1438338K` (3), `1029766A` (2), `1098478D` (2), … +16 more |
| BATIMENT ET TRAVAUX PUBLICS | registre_commerce | 20 | 12% | merge | `B01249542017` (5), `B13291997` (4), `B24145482012` (4), `B083219` (3), `B188841997` (3), … +15 more |
| CHIC | matricule_fiscal | 20 | 11% | merge | `1056547T` (5), `897753T` (4), `1598457F` (3), `1073857D` (2), `1081836V` (2), … +15 more |
| SELECTION | matricule_fiscal | 20 | 14% | merge | `991762A` (7), `1014887G` (4), `1325703L` (4), `1343433K` (4), `1048889S` (3), … +15 more |
| SOCIETE BEN-SALEM | matricule_fiscal | 20 | 13% | merge | `1154438M` (6), `949225L` (4), `967901C` (4), `1484348X` (3), `1184178C` (2), … +15 more |
| SOCIETE DE PROMOTION IMMOBILIERE AXIA | matricule_fiscal | 20 | 24% | merge | `750157V` (12), `1265121J` (6), `1264643C` (4), `635940Q` (4), `1260896F` (3), … +15 more |
| SOCIETE GENERAL DISTRIBUTION | matricule_fiscal | 20 | 14% | merge | `1032335E` (8), `819355Y` (6), `1315369M` (5), `1285658A` (4), `1409314P` (3), … +15 more |
| SOCIETE GENERAL VAP ET SERVICE | matricule_fiscal | 20 | 10% | merge | `622216Z` (4), `827373X` (4), `980422X` (3), `1132011S` (2), `1176496S` (2), … +15 more |
| SOCIETE GENERALE DE MENUISERIE SOGEM | matricule_fiscal | 20 | 18% | merge | `968189G` (9), `420354M` (7), `1353970M` (3), `36847K` (3), `789331W` (3), … +15 more |
| SOCIETE MABROUK | matricule_fiscal | 20 | 33% | merge | `580188F` (24), `1177809T` (6), `1165483C` (4), `966567E` (4), `1315583R` (3), … +15 more |
| GENERAL IMMOBILIERE DE L'AVENIR | matricule_fiscal | 19 | 20% | merge | `1085827L` (9), `340639L` (4), `1173360N` (3), `1313318R` (3), `1009175W` (2), … +14 more |
| MS SERVICES | matricule_fiscal | 19 | 17% | merge | `1295119G` (7), `1180463M` (3), `1102931K` (2), `1192043J` (2), `1259343J` (2), … +14 more |
| PNEU | matricule_fiscal | 19 | 17% | merge | `1145573S` (10), `2172E` (9), `1011295Z` (6), `1078824Q` (4), `1161611Z` (4), … +14 more |
| SOCIETE CONTACT | registre_commerce | 19 | 20% | merge | `B02124702015` (15), `B013011997` (8), `B0350582007` (8), `B2433842009` (7), `B0311002013` (5), … +14 more |
| SOCIETE GLOBE | matricule_fiscal | 19 | 11% | merge | `1263303E` (5), `323694M` (5), `774310N` (4), `11156421X` (3), `1188404K` (3), … +14 more |
| SOCIETE YOSR | matricule_fiscal | 19 | 30% | merge | `587499Z` (13), `1050714P` (5), `1448814Y` (5), `587599Z` (4), `1363935P` (3), … +14 more |
| STEP | matricule_fiscal | 19 | 18% | merge | `969271D` (10), `1251519F` (5), `488136W` (4), `999308Q` (4), `1184719K` (3), … +14 more |
| AS DE COMMERCE INTERNATIONAL | matricule_fiscal | 18 | 17% | merge | `1211840Q` (7), `1188099X` (4), `1179125E` (2), `1189910D` (2), `1206459F` (2), … +13 more |
| AZIZA | matricule_fiscal | 18 | 19% | merge | `968444G` (8), `1034663C` (4), `1488982L` (3), `1117381D` (2), `1125265X` (2), … +13 more |
| EL FAOUZ | matricule_fiscal | 18 | 20% | merge | `1017737F` (11), `963770S` (7), `612789D` (4), `1089161H` (3), `1226155C` (3), … +13 more |
| ENTREPRISE DE TRAVAUX ELECTRIQUES | matricule_fiscal | 18 | 23% | merge | `1338079D` (10), `1267543M` (4), `1063168D` (2), `1100015X` (2), `1118961Y` (2), … +13 more |
| ERRAHMA | matricule_fiscal | 18 | 69% | merge | `884195R` (58), `1109154X` (2), `1188441Q` (2), `1340815H` (2), `13619421E` (2), … +13 more |
| LE PROGRES | matricule_fiscal | 18 | 16% | merge | `854453Z` (8), `614801P` (6), `433488V` (5), `1090478T` (4), `1269316L` (3), … +13 more |
| MAS MAINTENANCE ET SERVICE | matricule_fiscal | 18 | 15% | merge | `864850P` (7), `1109421X` (4), `1367250H` (3), `582402A` (3), `790248T` (3), … +13 more |
| ME CONSULTANTS | matricule_fiscal | 18 | 23% | merge | `980692T` (17), `761845Y` (9), `1299448P` (7), `775137Y` (6), `1302629V` (5), … +13 more |
| MED SERVICES | matricule_fiscal | 18 | 24% | merge | `1024919C` (13), `1057827D` (5), `792176D` (5), `1253413E` (4), `1024749C` (2), … +13 more |
| SARA DE DISTRIBUTION | matricule_fiscal | 18 | 25% | merge | `1177471M` (13), `1021301J` (5), `1473876H` (4), `1235270F` (3), `1102633C` (2), … +13 more |
| SOCIETE ANIS | matricule_fiscal | 18 | 18% | merge | `797092X` (8), `1485476J` (4), `1189749N` (3), `1296386E` (3), `135981C` (3), … +13 more |
| SOCIETE ASMA | matricule_fiscal | 18 | 18% | merge | `1414847Z` (7), `778929M` (4), `1123535R` (2), `1190424K` (2), `1214105C` (2), … +13 more |
| SOCIETE CHEMS DE TRANSPORT DE MARCHANDISES | matricule_fiscal | 18 | 14% | merge | `752970B` (6), `703062Z` (5), `1117235T` (4), `30798S` (4), `362877K` (4), … +13 more |
| SOCIETE COMPTOIR DE BOIS | matricule_fiscal | 18 | 18% | merge | `1229145N` (10), `1143223N` (5), `1272543W` (5), `1035789W` (4), `1140506J` (4), … +13 more |
| SOCIETE DE NUTRITION | matricule_fiscal | 18 | 21% | merge | `842437K` (11), `2992K` (5), `1474874K` (3), `1519065A` (3), `1544260Z` (3), … +13 more |
| SOCIETE F H SERVICES | matricule_fiscal | 18 | 10% | merge | `1373723J` (4), `857967K` (4), `1092577E` (3), `1461340P` (3), `1017500K` (2), … +13 more |
| SOCIETE LE RECOUVREMENT | registre_commerce | 18 | 17% | merge | `B19512001` (15), `B126472002` (10), `B159212002` (8), `B138512002` (7), `B114972001` (6), … +13 more |
| SOCIETE ZIED | matricule_fiscal | 18 | 16% | merge | `1411373X` (7), `1333716N` (4), `1488292Q` (3), `1587249P` (3), `997580X` (3), … +13 more |
| GROUPEMENT AGRICOLE | matricule_fiscal | 17 | 17% | merge | `948916D` (21), `881400N` (18), `755962P` (15), `635666R` (11), `1005384L` (8), … +12 more |
| GS COMPANY INTERNATIONAL | registre_commerce | 17 | 12% | merge | `B0378712016` (5), `B01211812015` (3), `B02414832011` (3), `B037871216` (3), `B1107121996` (3), … +12 more |
| JUNIOR | matricule_fiscal | 17 | 21% | merge | `937275H` (11), `1025883M` (6), `975311G` (6), `1295925F` (3), `1556760E` (3), … +12 more |
| PREMIUM | matricule_fiscal | 17 | 15% | merge | `1249877F` (6), `1274758T` (5), `1426711X` (4), `1017041D` (2), `1113086G` (2), … +12 more |
| SERVICES INTERNATIONAL BSIR TOTALEMENT EXPORTATRICE SIB | registre_commerce | 17 | 16% | merge | `B2469502006` (8), `B198252010` (6), `B912182014` (6), `B2445722007` (5), `B11901998` (4), … +12 more |
| SOCIETE REAL ESTATE | matricule_fiscal | 17 | 14% | merge | `1104105Q` (7), `1010815X` (5), `1227214A` (5), `1179884P` (4), `1569728Y` (4), … +12 more |
| SOCIETE TUNISIE CONFECTION | matricule_fiscal | 17 | 18% | merge | `1060146J` (7), `1362469E` (4), `1181469Y` (3), `1199748S` (3), `601695N` (3), … +12 more |
| CENTRAL | matricule_fiscal | 16 | 23% | merge | `1287385C` (12), `986737Q` (7), `1184329Z` (5), `9247M` (5), `1503636L` (3), … +11 more |
| EL HOUDA | matricule_fiscal | 16 | 22% | merge | `644485P` (10), `635896E` (4), `928674T` (4), `341510P` (3), `966576F` (3), … +11 more |
| ENTREPRISE EL-AMEN | registre_commerce | 16 | 17% | merge | `B13195922010` (15), `B198751998` (15), `B127241997` (9), `B140851998` (8), `B24169352010` (8), … +11 more |
| EQUIPEMENT GENERAL DE BATIMENT EXPORT EGBE | matricule_fiscal | 16 | 17% | merge | `932147D` (6), `910594E` (5), `740178V` (3), `1029497Y` (2), `1213051B` (2), … +11 more |
| GROUPEMENT AGRICOLE | registre_commerce | 16 | 14% | merge | `B146842001` (15), `B14082003` (13), `B120732002` (10), `B2416832004` (10), `B0213652006` (8), … +11 more |
| N TRAINING | registre_commerce | 16 | 13% | merge | `B2456112012` (5), `B2459372007` (4), `B24100552009` (3), `B242462005` (3), `B25104762009` (3), … +11 more |
| PHENIX | matricule_fiscal | 16 | 17% | merge | `840725G` (9), `920386D` (7), `1261734R` (6), `1393399D` (4), `510648A` (4), … +11 more |
| PRIME SERVICES INFORMATIQUES | matricule_fiscal | 16 | 12% | merge | `1112064W` (4), `980688Y` (4), `1037704G` (3), `1080787Z` (2), `1230073F` (2), … +11 more |
| SOCIETE AMEL | registre_commerce | 16 | 18% | merge | `B1105921996` (7), `B0735872005` (6), `B195561997` (5), `60350662007` (3), `B01164092013` (3), … +11 more |
| SOCIETE DES SERVICES GENERAUX SSG | matricule_fiscal | 16 | 18% | merge | `1019630D` (6), `1037992F` (2), `1119012N` (2), `1127575S` (2), `1148157S` (2), … +11 more |
| SOCIETE LES AMIS | matricule_fiscal | 16 | 19% | merge | `1177553N` (8), `1509857Z` (6), `1415607N` (3), `1459940N` (3), `981321X` (3), … +11 more |
| SOCIETE MUTUELLE DES BASES DES SERVICES AGRICOLES | registre_commerce | 16 | 12% | merge | `011611998` (4), `B0475832008` (4), `B1137231997` (4), `B1614212006` (4), `B3931995` (3), … +11 more |
| SOCIETE SALMA | matricule_fiscal | 16 | 27% | merge | `612787B` (12), `1059762M` (6), `1031764T` (2), `1078477R` (2), `1127497W` (2), … +11 more |
| SOCIETE SOLTANA | matricule_fiscal | 16 | 14% | merge | `24120L` (5), `1335434P` (3), `1003017F` (2), `1078518H` (2), `1105812R` (2), … +11 more |
| SOCIETE YESMINE | matricule_fiscal | 16 | 22% | merge | `944007F` (11), `1233140M` (6), `1084688P` (3), `1215498P` (3), `1438460L` (3), … +11 more |
| SOLUTION T | registre_commerce | 16 | 11% | merge | `B0854272008` (4), `B0943372014` (4), `03168512013` (3), `B01228492013` (3), `B24147022011` (3), … +11 more |
| ALL MARKETING SERVICES | matricule_fiscal | 15 | 15% | merge | `1198173V` (6), `1127595X` (5), `1035955R` (4), `1542928N` (3), `544880Q` (3), … +10 more |
| AYA DISTRIBUTION | matricule_fiscal | 15 | 17% | merge | `1197547B` (6), `1102566J` (4), `1251425A` (3), `1301874C` (3), `1198136P` (2), … +10 more |
| EL AMEL | matricule_fiscal | 15 | 22% | merge | `1014246C` (9), `1115258S` (7), `609751N` (4), `1105745Y` (3), `1290219N` (2), … +10 more |
| EL MEDINA | matricule_fiscal | 15 | 11% | merge | `1061815D` (4), `615054G` (4), `1148493G` (3), `759554T` (3), `1194268J` (2), … +10 more |
| GLOBAL DISTRIBUTION | matricule_fiscal | 15 | 18% | merge | `866255J` (9), `418157N` (8), `1495802H` (5), `1463589Y` (4), `1109653M` (3), … +10 more |
| KMG SERVICES | matricule_fiscal | 15 | 24% | merge | `1364584Q` (9), `1327995Y` (3), `1231141E` (2), `1270427J` (2), `1306352B` (2), … +10 more |
| NESRINE | matricule_fiscal | 15 | 11% | merge | `1360328H` (3), `1217391M` (2), `1266529K` (2), `1330114D` (2), `1345156R` (2), … +10 more |
| SOCIETE AMINA | matricule_fiscal | 15 | 11% | merge | `1350590Q` (4), `708427F` (4), `1118335B` (3), `1441290L` (3), `943107E` (3), … +10 more |
| SOCIETE HAMZA | matricule_fiscal | 15 | 9% | merge | `1253571T` (3), `1324193G` (3), `1580124W` (3), `1188249S` (2), `1190522L` (2), … +10 more |
| SOCIETE SFAX PEINTURE ET DECORATION | matricule_fiscal | 15 | 10% | merge | `1521592T` (3), `1003993Y` (2), `1056677A` (2), `1122818W` (2), `1124548B` (2), … +10 more |
| SUD SUD TRAVAUX | matricule_fiscal | 15 | 13% | merge | `1306965B` (4), `1021725F` (3), `1131357N` (3), `1376487E` (3), `1166328W` (2), … +10 more |
| AB PROMOTION IMMOBILIERE | matricule_fiscal | 14 | 17% | merge | `956311A` (8), `1325482S` (7), `970455B` (6), `830060G` (5), `1468233S` (4), … +9 more |
| GALLAND ETABLISSEMENT STABLE | matricule_fiscal | 14 | 44% | merge | `968975B` (14), `1194038W` (3), `1297377H` (3), `710975B` (2), `765122K` (2), … +9 more |
| INTERNATIONAL PROD SIGN COMPANY TUNISIA | matricule_fiscal | 14 | 23% | merge | `1142790M` (7), `601426S` (6), `1410775H` (3), `1074561T` (2), `1102146R` (2), … +9 more |
| INTERNATIONAL TA CONSULTING | matricule_fiscal | 14 | 8% | merge | `1157392D` (2), `1182653A` (2), `1382502Y` (2), `1387841M` (2), `1479120T` (2), … +9 more |
| MAC INTERNATIONAL | registre_commerce | 14 | 15% | merge | `B252302007` (6), `B0330302006` (4), `B149611997` (4), `B1592572007` (4), `B24138722011` (4), … +9 more |
| OIL SERVICES | matricule_fiscal | 14 | 14% | merge | `908971P` (5), `1114826Z` (4), `1226363R` (4), `430013Y` (4), `1222363R` (3), … +9 more |
| PANORAMA | matricule_fiscal | 14 | 14% | merge | `905539N` (4), `296329M` (3), `1337403Q` (2), `1452580D` (2), `1453850L` (2), … +9 more |
| SARA SERVICES | matricule_fiscal | 14 | 17% | merge | `1405157C` (5), `1121118T` (2), `1256558K` (2), `1390519E` (2), `1402614T` (2), … +9 more |
| SERVICES AFRICA | matricule_fiscal | 14 | 23% | merge | `1190514L` (10), `1062374D` (5), `1030521W` (4), `1020216J` (3), `1097196R` (3), … +9 more |
| SOCIETE AGRICOLE EL-BARAKA | matricule_fiscal | 14 | 14% | merge | `824488V` (4), `1360514H` (3), `1005927W` (2), `1319861M` (2), `1409566J` (2), … +9 more |
| SOCIETE ARTISANALE AL-BARAKA | matricule_fiscal | 14 | 33% | merge | `1006426H` (17), `1041099N` (12), `1447181H` (6), `1047024T` (2), `1061967V` (2), … +9 more |
| SOCIETE DE TRAVAUX INDUSTRIELS | matricule_fiscal | 14 | 38% | merge | `975285Y` (18), `418561X` (4), `1075106C` (3), `1441633T` (3), `389086B` (3), … +9 more |
| SOCIETE MB DISTRIBUTION | matricule_fiscal | 14 | 15% | merge | `1012128N` (6), `1285005R` (5), `852705R` (5), `1062654J` (4), `1358083K` (4), … +9 more |
| SOCIETE NEGOCE INTERNATIONAL | registre_commerce | 14 | 18% | merge | `B03197982010` (6), `B12632003` (6), `B113402002` (4), `D241852007` (3), `B181421996` (2), … +9 more |
| SPEED | registre_commerce | 14 | 21% | merge | `B2434302007` (13), `B01258392016` (6), `B123382002` (6), `B147352002` (6), `B2445292005` (6), … +9 more |
| TRADE SERVICES | matricule_fiscal | 14 | 19% | merge | `608132L` (7), `1100998X` (4), `869399N` (4), `437522W` (3), `1002001S` (2), … +9 more |
| VENUS | matricule_fiscal | 14 | 29% | merge | `875973K` (12), `1351470M` (6), `1129683E` (3), `1387982A` (3), `1067250N` (2), … +9 more |
| AZUR | registre_commerce | 13 | 21% | merge | `B2684342008` (7), `B2415252009` (6), `B01151692016` (3), `B0133452007` (3), `B0358362005` (3), … +8 more |
| CHAMS | matricule_fiscal | 13 | 17% | merge | `1158536F` (6), `9233F` (4), `1117131L` (3), `1214738G` (3), `923828X` (3), … +8 more |
| EAGLE INTERNATIONAL TRADING COMPANY | matricule_fiscal | 13 | 8% | merge | `1131115W` (2), `1210775V` (2), `1230291P` (2), `1351884G` (2), `1353004X` (2), … +8 more |
| EL AMEL | registre_commerce | 13 | 33% | merge | `B1112591998` (11), `B0350862007` (5), `B140191998` (4), `B181321998` (3), `B114322002` (2), … +8 more |
| ETABLISSEMENT GHORBEL | matricule_fiscal | 13 | 13% | merge | `1068472F` (3), `1035641A` (2), `1400355K` (2), `1410851C` (2), `1438797K` (2), … +8 more |
| LA PRECISION MECANIQUE | matricule_fiscal | 13 | 12% | merge | `1109331W` (4), `1177100L` (4), `967819K` (4), `10420Y` (3), `1033802Q` (2), … +8 more |
| LA TUNISIENNE | matricule_fiscal | 13 | 32% | merge | `536917P` (12), `25612G` (5), `1191413L` (3), `580238A` (3), `1037292H` (2), … +8 more |
| LE RESEAU | matricule_fiscal | 13 | 26% | merge | `1406193L` (10), `1012896Z` (6), `1106189W` (4), `539151D` (3), `1112784Y` (2), … +8 more |
| LES HORIZONS | matricule_fiscal | 13 | 12% | merge | `1556071K` (4), `1122777E` (3), `1334844A` (3), `1522735V` (3), `867735A` (3), … +8 more |
| MTC DISTRIBUTION | matricule_fiscal | 13 | 32% | merge | `921426Y` (14), `1398665Z` (6), `1146570T` (5), `1423972E` (3), `1097779K` (2), … +8 more |
| NOUR DE COMMERCE | matricule_fiscal | 13 | 15% | merge | `1011690G` (4), `1213637Y` (2), `1223534X` (2), `1327138M` (2), `1418789Z` (2), … +8 more |
| PROMED | matricule_fiscal | 13 | 14% | merge | `1099803A` (4), `710820G` (4), `1167779A` (3), `916085N` (3), `1058670E` (2), … +8 more |
| SICAV ENTREPRISE | matricule_fiscal | 13 | 26% | merge | `1055155B` (13), `492474R` (7), `770729W` (6), `632956L` (5), `1076646G` (3), … +8 more |
| SOCIETE AMEUR | registre_commerce | 13 | 30% | merge | `B170131997` (14), `B247502008` (8), `B0251892004` (6), `B115371996` (3), `B25178872011` (3), … +8 more |
| SOCIETE BW TRADE COMPANY | registre_commerce | 13 | 32% | merge | `B0932162005` (11), `B03187392016` (5), `B0316140215` (3), `B24164102009` (3), `B2414802007` (2), … +8 more |
| SOCIETE CHAIMA | matricule_fiscal | 13 | 36% | merge | `1039666C` (21), `1048157L` (9), `1042834A` (6), `1042634A` (4), `1261612G` (4), … +8 more |
| SOCIETE CIVILE IMMOBILIERE | registre_commerce | 13 | 24% | merge | `B0289792013` (8), `C0155972008` (6), `C0139792005` (3), `C0159412003` (3), `C0351752007` (3), … +8 more |
| SOCIETE COMPTOIR DU SUD | matricule_fiscal | 13 | 18% | merge | `1166034J` (6), `1216161V` (4), `418711S` (3), `859977W` (3), `9613321P` (3), … +8 more |
| SOCIETE DE DISTRIBUTION ET DE SERVICE | matricule_fiscal | 13 | 19% | merge | `1047453M` (7), `1460645A` (4), `1472843T` (4), `1599979H` (3), `757639P` (3), … +8 more |
| SOCIETE FOOD SERVICES | matricule_fiscal | 13 | 24% | merge | `1048991P` (10), `1058460W` (7), `1224532Z` (5), `1466912B` (3), `1075509T` (2), … +8 more |
| SOCIETE INTERACTIVE | matricule_fiscal | 13 | 24% | merge | `911130D` (10), `601887V` (7), `985048R` (4), `136242A` (3), `989017B` (3), … +8 more |
| SOCIETE LE LABO | matricule_fiscal | 13 | 21% | merge | `1121630F` (7), `1100532P` (4), `1033912W` (2), `1057047G` (2), `1240201A` (2), … +8 more |
| SOCIETE MUTUELLE DES BASES DES SERVICES AGRICOLES | matricule_fiscal | 13 | 13% | merge | `1330554A` (4), `318026W` (4), `39642L` (4), `1287686N` (3), `1484641Z` (2), … +8 more |
| SOCIETE RAHMA SERVICES | matricule_fiscal | 13 | 24% | merge | `1016911X` (9), `487623C` (7), `1386155R` (4), `1536056A` (3), `1303818C` (2), … +8 more |
| SOCIETE SINDBAD | matricule_fiscal | 13 | 22% | merge | `1464437L` (8), `1047255H` (5), `33420X` (4), `1075736D` (3), `1471358F` (3), … +8 more |
| SOCIETE SIRINE | matricule_fiscal | 13 | 22% | merge | `543776M` (9), `1197390Y` (6), `833559T` (5), `1593035P` (4), `1093680G` (2), … +8 more |
| SOCIETE SPORT ET LOISIRS | matricule_fiscal | 13 | 14% | merge | `1393054E` (4), `1425590C` (4), `1412265Y` (3), `960770E` (3), `13340030F` (2), … +8 more |
| SOCIETE TRA SERVICES | matricule_fiscal | 13 | 12% | merge | `1007280M` (3), `1180973F` (2), `1186784D` (2), `1226614J` (2), `1321189Y` (2), … +8 more |
| TUNISIE DISTRIBUTION | registre_commerce | 13 | 30% | merge | `B140032002` (13), `B154332003` (8), `B1157001997` (6), `B0228062006` (5), `B154761996` (3), … +8 more |
| AB CORPORATION | registre_commerce | 12 | 34% | merge | `B0162742014` (15), `B2744242010` (5), `B24154152011` (4), `B2422112007` (4), `B01199202011` (3), … +7 more |
| AMAL SERVICES | matricule_fiscal | 12 | 17% | merge | `1387857W` (4), `1048468Z` (2), `1208059B` (2), `1217815Q` (2), `1276510D` (2), … +7 more |
| CARTHAGO SA | registre_commerce | 12 | 27% | merge | `B125432011` (10), `B2422622004` (7), `B157572002` (5), `B14462003` (3), `B162372001` (3), … +7 more |
| COSMOS | matricule_fiscal | 12 | 16% | merge | `1013852Q` (5), `1347030L` (4), `1227369V` (3), `1389678D` (3), `1504826V` (3), … +7 more |
| EL HAJ DES TRAVAUX PUBLICS | matricule_fiscal | 12 | 14% | merge | `1386161P` (3), `1286722V` (2), `1296259Y` (2), `1376435R` (2), `1426773M` (2), … +7 more |
| FARAH | registre_commerce | 12 | 38% | merge | `B134802003` (17), `B110671997` (9), `B151302002` (5), `B07107082009` (3), `B02209412012` (2), … +7 more |
| GENERAL IMMOBILIERE DE L'AVENIR | registre_commerce | 12 | 25% | merge | `B8111272009` (7), `B01164562013` (3), `B01217942017` (3), `B81186452010` (3), `B015422005` (2), … +7 more |
| GENERAL SERVICES AUTOS GSA | matricule_fiscal | 12 | 17% | merge | `1016198W` (4), `1312445T` (3), `1020336R` (2), `1131899Q` (2), `1173609V` (2), … +7 more |
| HORIZON 2002 | matricule_fiscal | 12 | 19% | merge | `1201359F` (8), `418136H` (8), `1303493B` (6), `1537442L` (5), `1478753T` (4), … +7 more |
| KZ PETROLEUM SERVICES | matricule_fiscal | 12 | 12% | merge | `1028145W` (5), `1129465W` (5), `1178536R` (5), `398144V` (5), `1265561F` (4), … +7 more |
| LA FONDATION | matricule_fiscal | 12 | 19% | merge | `587880A` (6), `835118E` (5), `1064381L` (4), `1459908N` (3), `1028177E` (2), … +7 more |
| LA TUNISIENNE | registre_commerce | 12 | 41% | merge | `B116451996` (12), `B4481996` (5), `B187242000` (3), `8116451996` (2), `B11645` (2), … +7 more |
| LE FORUM | matricule_fiscal | 12 | 26% | merge | `341542Y` (9), `1249295N` (5), `17519P` (5), `496235V` (3), `1227089P` (2), … +7 more |
| NEW TECHNOLOGY ET SERVICES | matricule_fiscal | 12 | 27% | merge | `1346877Z` (8), `1226989P` (3), `1425226J` (3), `1090939C` (2), `1310662S` (2), … +7 more |
| RANIM | matricule_fiscal | 12 | 25% | merge | `1351380L` (7), `1105069J` (2), `1116658K` (2), `1137437N` (2), `1210708H` (2), … +7 more |
| SICAF + | matricule_fiscal | 12 | 34% | merge | `381564B` (22), `496267D` (12), `433734P` (6), `40789X` (5), `496214P` (5), … +7 more |
| SICAF + | registre_commerce | 12 | 36% | merge | `B199991996` (19), `B1681996` (10), `B112811997` (5), `B119171996` (5), `B19381` (3), … +7 more |
| SOCIETE AL-AMIRA | matricule_fiscal | 12 | 24% | merge | `749148C` (6), `1193605B` (2), `1249689D` (2), `1291729L` (2), `1325438N` (2), … +7 more |
| SOCIETE AMEUR | matricule_fiscal | 12 | 24% | merge | `1037211P` (8), `1218909A` (6), `539369W` (3), `882091A` (3), `936833M` (3), … +7 more |
| SOCIETE CHEMS DE TRANSPORT DE MARCHANDISES | registre_commerce | 12 | 21% | merge | `B15662001` (6), `B1124091997` (4), `B117461997` (4), `B2721482008` (3), `B126492001` (2), … +7 more |
| SOCIETE CIVILE IMMOBILIERE | matricule_fiscal | 12 | 28% | merge | `1196071F` (12), `796816F` (8), `1312254N` (6), `765773R` (3), `819746K` (3), … +7 more |
| SOCIETE DE PROMOTION IMMOBILIERE AXIA | registre_commerce | 12 | 44% | merge | `B188172000` (14), `B24173452012` (4), `B128872001` (3), `B2415422005` (3), `B113782002` (1), … +7 more |
| SOCIETE EL-KHADRA | matricule_fiscal | 12 | 30% | merge | `6473H` (12), `1094798A` (8), `1276176K` (4), `1310505E` (2), `1399195T` (2), … +7 more |
| SOCIETE EL-WIFAK | registre_commerce | 12 | 20% | merge | `B1124851997` (4), `R164762000` (3), `B131042252012` (2), `B25184212011` (2), `D014062010` (2), … +7 more |
| SOCIETE ENTREPRISE TRABELSI | registre_commerce | 12 | 18% | merge | `B0770222013` (6), `B166081998` (6), `B2510972004` (5), `B1119891998` (4), `B148002000` (3), … +7 more |
| SOCIETE EZDIHAR | matricule_fiscal | 12 | 19% | merge | `1173444R` (6), `1008211C` (4), `743724M` (4), `1383415E` (3), `1191950H` (2), … +7 more |
| SOCIETE HAMMAMI POUR LE COMMERCE DES MEUBLES USAGES | registre_commerce | 12 | 55% | merge | `B1134041997` (26), `B119041998` (4), `B0152672004` (3), `B1456352005` (2), `B172791999` (2), … +7 more |
| SOCIETE INTERNATIONALE DE DISTRIBUTION | matricule_fiscal | 12 | 18% | merge | `326447L` (6), `1044137P` (4), `803835D` (4), `529097K` (3), `1193380D` (2), … +7 more |
| SOCIETE START | matricule_fiscal | 12 | 26% | merge | `1142207J` (9), `1319887Y` (3), `1372155T` (3), `1424426L` (3), `1512101J` (3), … +7 more |
| SOCIETE TOURISTIQUE ET HOTELIERE CARTHAGE STHC | registre_commerce | 12 | 18% | merge | `B167491999` (9), `B197511996` (9), `B188161996` (7), `B0175642010` (6), `B134841997` (6), … +7 more |
| SOCIETE TUNISIE CONCEPT | matricule_fiscal | 12 | 17% | merge | `1057966P` (6), `1004485L` (5), `100448S` (4), `1188572B` (4), `1059019L` (3), … +7 more |
| SOCIETE TUNISIENNE DE COMMERCE | matricule_fiscal | 12 | 14% | merge | `1118169F` (3), `1501412M` (3), `1286985S` (2), `1335466N` (2), `1340131K` (2), … +7 more |
| SUD SUD TRAVAUX | registre_commerce | 12 | 47% | merge | `B2538972007` (24), `B2155892006` (4), `B2411372010` (4), `B02231582014` (3), `B11095619000` (3), … +7 more |
| AL IZ AGRICOLE | matricule_fiscal | 11 | 15% | merge | `1204176N` (4), `1284965E` (3), `1550384Z` (3), `1195477W` (2), `1339803M` (2), … +6 more |
| ALAA SERVICES | matricule_fiscal | 11 | 14% | merge | `1531724S` (3), `11178131Q` (2), `1200671G` (2), `1202233W` (2), `1269985K` (2), … +6 more |
| EL HANA | registre_commerce | 11 | 22% | merge | `B2213182004` (8), `B180142000` (7), `B015942004` (4), `B130501996` (4), `B2056892005` (4), … +6 more |
| H ET R TEXTILE | matricule_fiscal | 11 | 22% | merge | `1026590F` (6), `1119039A` (3), `1482934B` (3), `983934C` (3), `1008340L` (2), … +6 more |
| INTERNATIONAL PROD SIGN COMPANY TUNISIA | registre_commerce | 11 | 53% | merge | `B152451997` (19), `B01136842015` (3), `B2489642008` (3), `801166832010` (2), `B0144732009` (2), … +6 more |
| MBM INFORMATIQUE ET SERVICES | matricule_fiscal | 11 | 10% | merge | `1296770J` (2), `1306144V` (2), `1338709L` (2), `1423897L` (2), `1449807D` (2), … +6 more |
| SOCIETE ALMA | matricule_fiscal | 11 | 19% | merge | `1539560A` (6), `1139174S` (5), `1113716P` (4), `1190459X` (3), `1290723A` (2), … +6 more |
| SOCIETE COMPTOIR DU SUD | registre_commerce | 11 | 18% | merge | `B1101771997` (5), `B142951996` (5), `B081772004` (3), `B1108621997` (3), `B116501997` (3), … +6 more |
| SOCIETE DE MAINTENANCE GENERALE | matricule_fiscal | 11 | 25% | merge | `315741E` (7), `901363P` (3), `1025300A` (2), `1211646Q` (2), `1329644K` (2), … +6 more |
| SOCIETE DE PRODUITS ALIMENTAIRES SPA | registre_commerce | 11 | 30% | merge | `B095742007` (8), `B134911998` (5), `B0390812013` (2), `B146391997` (2), `B15197692012` (2), … +6 more |
| SOCIETE INTERNATIONALE DE SERVICES | matricule_fiscal | 11 | 27% | merge | `1156754F` (8), `1425308K` (4), `960965P` (3), `1102113G` (2), `1232345V` (2), … +6 more |
| SOCIETE LE FRIGO | registre_commerce | 11 | 23% | merge | `B08196602014` (6), `B112145` (3), `B1529152015` (3), `B1744852008` (3), `B24122582009` (3), … +6 more |
| SOCIETE LE LABORATOIRE | registre_commerce | 11 | 32% | merge | `B1192003` (10), `B2462522006` (7), `0181022016` (3), `B0824322004` (2), `B1130041997` (2), … +6 more |
| SOCIETE LIFE | registre_commerce | 11 | 71% | merge | `B1116511996` (55), `B0134832005` (5), `B24154562009` (4), `B091952006` (3), `B0109422014` (2), … +6 more |
| SOCIETE LINA | registre_commerce | 11 | 18% | merge | `B02192922016` (5), `1524462010` (4), `B078062013` (3), `B24141752001` (3), `B2415742007` (3), … +6 more |
| SOCIETE MEGA | registre_commerce | 11 | 25% | merge | `B139401996` (11), `B019932006` (8), `B113771997` (5), `B01191952013` (4), `B187952000` (4), … +6 more |
| SOCIETE MODERNE DE DISTRIBUTION | matricule_fiscal | 11 | 15% | merge | `1231247P` (4), `1435448C` (3), `1435488L` (3), `1511186C` (3), `111856W` (2), … +6 more |
| SOCIETE VITAL | matricule_fiscal | 11 | 14% | merge | `979190J` (4), `1214216J` (3), `1490089K` (3), `712802N` (3), `748728N` (3), … +6 more |
| SOGECO | matricule_fiscal | 11 | 20% | merge | `2011M` (5), `1425086Q` (4), `411618R` (3), `1042231C` (2), `1042241E` (2), … +6 more |
| TRADING COMPANY TUNISIA TCT | matricule_fiscal | 11 | 21% | merge | `1184265A` (8), `947964H` (8), `1031283F` (4), `1057630R` (4), `1362487G` (3), … +6 more |
| TUNISIE TEXTILE | matricule_fiscal | 11 | 26% | merge | `381645B` (9), `1399462T` (4), `736433L` (4), `1327318P` (3), `753600F` (3), … +6 more |
| UNIVERSAL TRADING | matricule_fiscal | 11 | 15% | merge | `1187752Z` (4), `1406667A` (3), `1481667X` (3), `1485685R` (3), `1022450B` (2), … +6 more |
| AGRO SERVICES | matricule_fiscal | 10 | 28% | merge | `1130081Z` (8), `1278794Q` (5), `1438666Z` (3), `1090393P` (2), `1165691J` (2), … +5 more |
| ANDY ENGINEERING TUNISIA | matricule_fiscal | 10 | 32% | merge | `1200084S` (11), `1187203Y` (6), `1064042T` (3), `1181374R` (3), `10640421A` (2), … +5 more |
| B R ET COMPANY | matricule_fiscal | 10 | 15% | merge | `1104278M` (3), `835567C` (3), `1375209D` (2), `1427726J` (2), `1538658F` (2), … +5 more |
| BEST TELECOM SERVICES | matricule_fiscal | 10 | 22% | merge | `1486868B` (4), `11379451E` (2), `1219247N` (2), `1233940N` (2), `1421205L` (2), … +5 more |
| BRAVO | matricule_fiscal | 10 | 32% | merge | `858784J` (17), `1179783K` (13), `1147350M` (7), `749429J` (4), `1335480W` (3), … +5 more |
| EL BARAKA DISTRIBUTION | matricule_fiscal | 10 | 17% | merge | `1342144Z` (3), `1252649V` (2), `1304174S` (2), `1396708J` (2), `1445826P` (2), … +5 more |
| EL FATH | matricule_fiscal | 10 | 13% | merge | `1282808H` (2), `1290516V` (2), `1382483N` (2), `1516569L` (2), `983473X` (2), … +5 more |
| EL WIFEK | registre_commerce | 10 | 19% | merge | `B129781996` (3), `B0514372009` (2), `B09231232015` (2), `B26138392010` (2), `B9150152012` (2), … +5 more |
| FOOD DISTRIBUTION | matricule_fiscal | 10 | 13% | merge | `103200L` (4), `1032100L` (4), `1058747J` (4), `1282114H` (4), `1414083C` (4), … +5 more |
| GENERALE ELECTRIQUE | matricule_fiscal | 10 | 22% | merge | `1102394G` (5), `1128140X` (2), `1135293G` (2), `1361612N` (2), `1362416Q` (2), … +5 more |
| HM BUREAUTIQUE ET INFORMATIQUE | registre_commerce | 10 | 24% | merge | `B154701997` (5), `B03213202012` (3), `B15171682012` (3), `B014962012` (2), `B197161996` (2), … +5 more |
| HORIZON SERVICES | matricule_fiscal | 10 | 10% | merge | `1013282C` (2), `1104168G` (2), `1114473T` (2), `1116481C` (2), `1158135R` (2), … +5 more |
| INTERNATIONAL CITY CENTER | matricule_fiscal | 10 | 40% | merge | `341544A` (12), `1045341W` (3), `1184058V` (2), `1311955H` (2), `1343669N` (2), … +5 more |
| LA PERLE | registre_commerce | 10 | 22% | merge | `B03187502009` (4), `B127602003` (3), `B01169212013` (2), `B2457772007` (2), `B25197702010` (2), … +5 more |
| LA PROMOTION IMMOBILIERE PRIM | matricule_fiscal | 10 | 39% | merge | `1030973X` (18), `1123951E` (7), `1141266R` (4), `578546M` (4), `1068511V` (3), … +5 more |
| LA SOURCE | matricule_fiscal | 10 | 16% | merge | `1390345A` (3), `1021787W` (2), `1029705L` (2), `1139131F` (2), `1286076M` (2), … +5 more |
| LE PATRIMOINE | matricule_fiscal | 10 | 49% | merge | `745378Y` (15), `1125006D` (6), `11460765H` (2), `1302263J` (2), `1369707E` (2), … +5 more |
| LE PILOTE | matricule_fiscal | 10 | 23% | merge | `37603V` (6), `1603785F` (4), `1195167J` (3), `837803V` (3), `1320768H` (2), … +5 more |
| LINK | registre_commerce | 10 | 33% | merge | `B025042005` (11), `B25159372011` (11), `B1147652014` (2), `B2233692011` (2), `B2478302010` (2), … +5 more |
| LOGISTIC SERVICES | matricule_fiscal | 10 | 38% | merge | `608110E` (12), `1330632X` (4), `1095268G` (2), `1174590F` (2), `1247537D` (2), … +5 more |
| MG TRADING | matricule_fiscal | 10 | 14% | merge | `1392969M` (3), `989708Y` (3), `1302737Y` (2), `1402945L` (2), `1403157T` (2), … +5 more |
| MIA MIA DISTRIBUTION | matricule_fiscal | 10 | 23% | merge | `1394731Z` (6), `1561911K` (3), `1580741R` (3), `1274366F` (2), `1334442K` (2), … +5 more |
| MODA | registre_commerce | 10 | 21% | merge | `B03117592011` (4), `A1188671998` (2), `B0240342015` (2), `B0270152015` (2), `B03113892010` (2), … +5 more |
| SOCIETE AM DE SERVICE ET COMMERCE INTERNATIONALE NON RESIDENTE | registre_commerce | 10 | 25% | merge | `B0164922007` (10), `B249052007` (9), `B24211102010` (5), `D2423332007` (5), `B24183762009` (4), … +5 more |
| SOCIETE AMANI | matricule_fiscal | 10 | 19% | merge | `1455335E` (4), `515524K` (4), `1053292B` (2), `1274815K` (2), `1424340F` (2), … +5 more |
| SOCIETE HAIFA | matricule_fiscal | 10 | 26% | merge | `798547M` (10), `1130386P` (8), `870190N` (7), `939231D` (4), `1043636A` (2), … +5 more |
| SOCIETE HAMMAMI POUR LE COMMERCE DES MEUBLES USAGES | matricule_fiscal | 10 | 42% | merge | `6175A` (10), `539731T` (3), `1029409F` (2), `510814W` (2), `942100S` (2), … +5 more |
| SOCIETE IDEAL SERVICE | matricule_fiscal | 10 | 23% | merge | `382095X` (6), `1175319W` (4), `1361343L` (2), `1379919W` (2), `1451721T` (2), … +5 more |
| SOCIETE IMEN | registre_commerce | 10 | 21% | merge | `B2427702008` (6), `B183251996` (4), `B161012001` (3), `B2357742007` (3), `B1044782014` (2), … +5 more |
| SOCIETE JMF | matricule_fiscal | 10 | 17% | merge | `1089766H` (3), `1020630Q` (2), `1038396V` (2), `1181281M` (2), `1372202H` (2), … +5 more |
| SOCIETE MUTUELLE DE BASE DES SERVICES AGRICOLES EL-FALAH | matricule_fiscal | 10 | 17% | merge | `1598350V` (4), `1597067Q` (3), `580806J` (3), `1146925B` (2), `1191272R` (2), … +5 more |
| SOCIETE NADINE + | matricule_fiscal | 10 | 32% | merge | `635831L` (8), `1121398S` (2), `1151556E` (2), `1219842C` (2), `1332594S` (2), … +5 more |
| SOCIETE TOURISME ET LOISIRS | matricule_fiscal | 10 | 34% | merge | `296111V` (10), `1229793R` (5), `1516108J` (4), `312463N` (3), `1499392D` (2), … +5 more |
| SOCIETE TOURISTIQUE ET HOTELIERE CARTHAGE STHC | matricule_fiscal | 10 | 23% | merge | `646278S` (8), `1147557B` (6), `9912Y` (6), `13760E` (5), `12947K` (3), … +5 more |
| SOCIETE TUNISIE TRANSPORT | matricule_fiscal | 10 | 25% | merge | `1059240P` (7), `745274Q` (6), `46193Z` (3), `1250641C` (2), `1449242M` (2), … +5 more |
| SOMAC | matricule_fiscal | 10 | 15% | merge | `1173161H` (3), `1184741H` (3), `894317N` (3), `1048884M` (2), `1154275L` (2), … +5 more |
| SSAM INTERNATIONAL TRADE | matricule_fiscal | 10 | 29% | merge | `1139531T` (9), `708299R` (7), `1032082C` (2), `1125064P` (2), `1157405Q` (2), … +5 more |
| TUNISIA GOLF SERVICES | matricule_fiscal | 10 | 31% | merge | `1064613H` (11), `1370238M` (6), `985576M` (5), `1229672H` (3), `1186303J` (2), … +5 more |
| TUNISIE CAR | matricule_fiscal | 10 | 27% | merge | `815238B` (12), `949040D` (9), `1428617J` (8), `1157350S` (3), `9490400R` (3), … +5 more |
| YARA DE COMMERCE INTERNATIONAL | matricule_fiscal | 10 | 14% | merge | `1449898Z` (3), `1474932C` (3), `1204173K` (2), `1213219H` (2), `1335239N` (2), … +5 more |
| YKK TRADING TUNISIA | matricule_fiscal | 10 | 44% | merge | `614513J` (15), `1263975R` (3), `1393411F` (3), `1258431D` (2), `1273925L` (2), … +5 more |
| AL AMEN | matricule_fiscal | 9 | 30% | merge | `1441773B` (7), `1328221K` (2), `1397723M` (2), `1426086V` (2), `1445142R` (2), … +4 more |
| AM DISTRIBUTION | matricule_fiscal | 9 | 30% | merge | `1052975T` (7), `1075917G` (3), `1170712E` (2), `1256306Q` (2), `1276505A` (2), … +4 more |
| AUTO PIECES | registre_commerce | 9 | 22% | merge | `B121682002` (4), `B0332142008` (3), `B2736852006` (3), `B07130312012` (2), `B150932000` (2), … +4 more |
| CENTRAL | registre_commerce | 9 | 27% | merge | `B0146672013` (9), `B014082007` (5), `B110861996` (5), `B216191302010` (5), `B17646` (3), … +4 more |
| CHAARI INTERNATIONAL TRADE | matricule_fiscal | 9 | 24% | merge | `1164090J` (5), `1004775T` (3), `1351319F` (2), `1403804C` (2), `14193481F` (2), … +4 more |
| CHAMS | registre_commerce | 9 | 17% | merge | `B1148231997` (3), `B195301997` (3), `D11637` (3), `B1117711997` (2), `B8160742015` (2), … +4 more |
| COMPETENCES+ | matricule_fiscal | 9 | 23% | merge | `1266563M` (5), `1281155N` (3), `1189820C` (2), `1234163Z` (2), `1310511C` (2), … +4 more |
| CONCEPT DESIGN | matricule_fiscal | 9 | 18% | merge | `1165189Z` (5), `1430416X` (4), `1436544F` (4), `769763G` (4), `1181023V` (2), … +4 more |
| CONSULT INTERNATIONAL | matricule_fiscal | 9 | 33% | merge | `1013401Q` (8), `992709Z` (3), `1120792V` (2), `1154617N` (2), `1167953W` (2), … +4 more |
| DISCOVERY | matricule_fiscal | 9 | 20% | merge | `971451B` (4), `955323A` (3), `1124325M` (2), `1125906H` (2), `1298513B` (2), … +4 more |
| EL WAFA | registre_commerce | 9 | 19% | merge | `B029822006` (3), `B9198792009` (3), `B0223562013` (2), `B0821852015` (2), `B0861432007` (2), … +4 more |
| ELITE + | registre_commerce | 9 | 17% | merge | `B0120572017` (2), `B155322001` (2), `B31205312011` (2), `B0140542012` (1), `B03120822013` (1), … +4 more |
| ENNASR | matricule_fiscal | 9 | 24% | merge | `896345B` (4), `1189435X` (2), `1221226Q` (2), `1238813P` (2), `1292864N` (2), … +4 more |
| EQUIPEMENT GENERAL DE BATIMENT EXPORT EGBE | registre_commerce | 9 | 20% | merge | `B1134401997` (3), `B139602000` (3), `B00454372011` (2), `B116882001` (2), `81126721997` (1), … +4 more |
| EURO MED | matricule_fiscal | 9 | 21% | merge | `1006000J` (4), `1531825Y` (3), `1327136K` (2), `1475549D` (2), `1501661D` (2), … +4 more |
| FIMCO INTERNATIONAL | matricule_fiscal | 9 | 29% | merge | `632974N` (7), `1048432L` (3), `1096178K` (3), `1071217R` (2), `1129361N` (2), … +4 more |
| IMMOBILIERE EL-AMANA | matricule_fiscal | 9 | 26% | merge | `758809T` (5), `1071452B` (3), `1182883N` (2), `1292857Y` (2), `1566999H` (2), … +4 more |

_3848 further conflicts are in `org_identifiers.csv`, where `is_conflicting = 1`._
