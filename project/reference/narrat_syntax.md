# NARRAT SCRIPTING CHEATSHEET

## 1. CORE SYNTAX & CONCEPTS
- **Labels:** Define blocks of code. `main:` is the required entry point.
- **Indentation:** Defines branching depth. Must be strictly consistent!
- **Commands & Expressions:** Written as `command arg1 arg2`. Expressions returning values are wrapped in parenthesis: `(+ 2 3)`.
- **Variables (Global/State):** - **Get value:** Prefix with `$` (e.g., `$data.day`).
    - **Set/Pass path:** Do NOT use `$` (e.g., `set data.day 3`).
    - **Convention:** Store game variables inside the `data` object (e.g., `data.playerName`).
- **Local Variables:** Created with `var` and scoped to the current label only (e.g., `var myLocal 5`).
- **Multiline:** Use `\` at the end of a line to split long strings or commands.

## 2. DIALOGUE & NARRATIVE
- `talk [character] [pose] "Text"` : Makes a character speak.
    - *Example:* `talk player idle "Hello!"`
- `think [character] [pose] "Text"` : Inner monologue.
- `narrate "Text"` or just `"Text"` : Text from the game/narrator.
- `choice:` : Creates a branching choice menu.
  ```narrat
  choice:
    talk npc idle "Where to?"
    "Go to the forest":
      jump forest_label
    "Stay here":
      "You decided to stay."
      
## 3. FLOW CONTROL
- jump [label] : Stops current script and jumps to a label.
- run [label] [args...] : Runs a label like a function and returns to the current spot.
    - Example: var meal (run takeout_menu Pizza)
- return [value] : Returns a value from a label function.
- if [condition]: / else:: Standard branching logic.
  Example:
  if (> $data.money 10):
  "You can afford this!"
  else:
  "Too expensive."

## 4. VARIABLES & DATA STRUCTURES
- set [path] [value] : set data.health 100
- add [path] [value] : add data.score 10
- var [name] [value] : var tempScore 5
- Objects: Created automatically via dot notation or new Object.
    - Example: set data.player.name "Alice"
    - Dynamic Key: $data.myObject[$key]
- Arrays: Created via new Array.
    - Example: set data.inventory (new Array "Sword" "Shield")
    - Dynamic Index: $data.inventory[$index]

## 5. MATH & LOGIC
- Math Commands: +, -, *, /, min, max, clamp, floor, ceil, round, sqrt, ^
- Example: set data.damage (* 2 5)
- Logic Commands: ==, >, <, >=, <=, !=, !, &&, ||
- Ternary: ?
    - Example: var isDead (? (<= $data.life 0) true false)

## 6. ARRAY OPERATIONS
- push / pop / shift : push $data.inventory "Potion"
- array_join : array_join $data.inventory ", "
- includes : includes $data.inventory "Sword" (Returns true/false)
- slice, splice, reverse, shuffle, random_from_array
- Loops/Transforms: array_map, array_filter, array_reduce, array_find
    - (Note: These take a predicate label that receives element index array)

## 7. CORE GAMEPLAY FEATURES
- Audio: play music [id], pause music, stop music
- Items: - add_item [id] [amount]
    - remove_item [id] [amount]
    - has_item? [id] [amount] (Returns boolean)
    - item_amount? [id] (Returns int)
- Quests: start_quest [id], complete_quest [id], quest_completed? [id]
- Skills & Checks: - add_level [skill_id] [amount]
    - roll [check_id] [skill_id] [difficulty] (Returns boolean for skill check)
- Stats: add_stat [id] [amount], set_stat [id] [amount], get_stat_value [id]
- Viewport: set_screen [screen_id] [layer]
- Random: random [min] [max], random_float [min] [max]  
  