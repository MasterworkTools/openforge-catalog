#!/bin/bash

./dropbox_scanner --verbose --update=../openforge/db/fixtures/blueprints/aztlan.json --upload > ../openforge/db/fixtures/blueprints/aztlan.json.next
./dropbox_scanner --verbose --update=../openforge/db/fixtures/blueprints/bases.json --upload > ../openforge/db/fixtures/blueprints/bases.json.next
./dropbox_scanner --verbose --update=../openforge/db/fixtures/blueprints/building_facades.json --upload > ../openforge/db/fixtures/blueprints/building_facades.json.next
./dropbox_scanner --verbose --update=../openforge/db/fixtures/blueprints/catacombs.json --upload > ../openforge/db/fixtures/blueprints/catacombs.json.next
./dropbox_scanner --verbose --update=../openforge/db/fixtures/blueprints/cave.json --upload > ../openforge/db/fixtures/blueprints/cave.json.next
./dropbox_scanner --verbose --update=../openforge/db/fixtures/blueprints/cavern.json --upload > ../openforge/db/fixtures/blueprints/cavern.json.next
./dropbox_scanner --verbose --update=../openforge/db/fixtures/blueprints/cracked_ice.json --upload > ../openforge/db/fixtures/blueprints/cracked_ice.json.next
./dropbox_scanner --verbose --update=../openforge/db/fixtures/blueprints/cut-stone.json --upload > ../openforge/db/fixtures/blueprints/cut-stone.json.next
./dropbox_scanner --verbose --update=../openforge/db/fixtures/blueprints/cut-stone_ruined.json --upload > ../openforge/db/fixtures/blueprints/cut-stone_ruined.json.next
./dropbox_scanner --verbose --update=../openforge/db/fixtures/blueprints/dungeon_stone.json --upload > ../openforge/db/fixtures/blueprints/dungeon_stone.json.next
./dropbox_scanner --verbose --update=../openforge/db/fixtures/blueprints/dungeon_stone_ruined.json --upload > ../openforge/db/fixtures/blueprints/dungeon_stone_ruined.json.next
./dropbox_scanner --verbose --update=../openforge/db/fixtures/blueprints/dwarven_halls.json --upload > ../openforge/db/fixtures/blueprints/dwarven_halls.json.next
./dropbox_scanner --verbose --update=../openforge/db/fixtures/blueprints/encounters.json --upload > ../openforge/db/fixtures/blueprints/encounters.json.next
./dropbox_scanner --verbose --update=../openforge/db/fixtures/blueprints/legacy_sewers.json --upload > ../openforge/db/fixtures/blueprints/legacy_sewers.json.next
./dropbox_scanner --verbose --update=../openforge/db/fixtures/blueprints/mines.json --upload > ../openforge/db/fixtures/blueprints/mines.json.next
./dropbox_scanner --verbose --update=../openforge/db/fixtures/blueprints/pool.json --upload > ../openforge/db/fixtures/blueprints/pool.json.next
./dropbox_scanner --verbose --update=../openforge/db/fixtures/blueprints/rough_stone.json --upload > ../openforge/db/fixtures/blueprints/rough_stone.json.next
./dropbox_scanner --verbose --update=../openforge/db/fixtures/blueprints/rough_stone_ruined.json --upload > ../openforge/db/fixtures/blueprints/rough_stone_ruined.json.next
./dropbox_scanner --verbose --update=../openforge/db/fixtures/blueprints/sewers.json --upload > ../openforge/db/fixtures/blueprints/sewers.json.next
./dropbox_scanner --verbose --update=../openforge/db/fixtures/blueprints/streets.json --upload > ../openforge/db/fixtures/blueprints/streets.json.next
./dropbox_scanner --verbose --update=../openforge/db/fixtures/blueprints/towne.json --upload > ../openforge/db/fixtures/blueprints/towne.json.next

pushd ../openforge/db/fixtures/blueprints/
  rename -f 's/\.json\.next/.json/' *.json.next
popd
