# Character Status
<!-- evidence-id: status_sheet.character_status -->

# Femi D'survival
<!-- evidence-id: status_sheet.femi_d_survival -->

## Identity
<!-- evidence-id: status_sheet.femi_d_survival.identity -->
full name: Femi D'survival
age: 25
race: Human
class level: 1
normal level: 1
class XP: 0 / 200
normal XP: 0 / 500
Tier: 0

## Stats
<!-- evidence-id: status_sheet.femi_d_survival.stats -->
Str: 3
Agi: 5
End: 4
Int: 7
Wis: 7
Pre: 4

### Derived Stats
<!-- evidence-id: status_sheet.femi_d_survival.stats.derived_stats -->

HP = END × 5 = 4 × 5 = 20

MP = WIS × 5 = 7 × 5 = 35

SP = STR + END = 3 + 4 = 7

Strain = END + WIS = 4 + 7 = 11

Initiative = AGI + INT = 5 + 7 = 12

Carry Load = STR × 10 = 3 × 10 = 30

Physical Resist = END = 4

Magic Resist = INT + WIS = 7 + 7 = 14

Mental Resist = WIS = 7

Social Resist = PRE = 4

### Stat Modifiers
<!-- evidence-id: status_sheet.femi_d_survival.stats.stat_modifiers -->

Character tier: 0. Stat Modifier magnitude band for Tier 0: +1 to +2, a hard per-modifier bound.

Player-selected Stat Modifiers from the status_stat_modifiers setup batch. No unselected option is applied. Each entry is `breadth: broad_stat_domain` and applies to general actions within its stat domain. Relevant selected Stat Modifiers sum normally; no no-stacking, highest-single, or same-evidence exclusion applies unless a specific rule explicitly limits a combination.

#### AGI — Manual Coordination
<!-- evidence-id: status_sheet.femi_d_survival.stats.stat_modifiers.agi_manual_coordination -->
- slot: AGI slot 1 (AGI value 5)
- basis: low | breadth: broad_stat_domain | magnitude: +1 AGI (Tier 0 band +1 to +2)
- capability: General hand-eye and fine-motor coordination for precise physical manipulation, assembly, and coordinated two-hand tasks.
- evidence: Character draft: five years of home laboratory and workstation building implies practiced fine coordination; no dedicated agility training established.
- limitations: Not trained combat timing; precision degrades under stress or with unfamiliar tools.
- growth / conversion: Stays inside the Tier 0 band; a higher magnitude requires additional independent evidence and a documented Tier review. If play narrows it to a specific tool or profession, it converts to an Effect Modifier.

#### INT — Systems Analysis
<!-- evidence-id: status_sheet.femi_d_survival.stats.stat_modifiers.int_systems_analysis -->
- slot: INT slot 1 (INT value 7)
- basis: high | breadth: broad_stat_domain | magnitude: +2 INT (Tier 0 band +1 to +2)
- capability: Analysis of complex systems — mapping components, tracing dependencies, noticing contradictions and flaws, and predicting failure points across technical, procedural, and everyday problems.
- evidence: Character draft: applied AI engineer; built integrated rooftop solar, a 10 kWh battery bank, a 24 GB-VRAM workstation, an offline archive, and local automation; described as analytical and relentlessly curious about how systems fit together.
- limitations: Requires time and information; overanalysis can delay action under immediate threat.
- growth / conversion: +2 is the ceiling of the Tier 0 band; further magnitude requires additional independent evidence and a documented Tier review or breakthrough. If play narrows it to a specific tool, profession, or maneuver, it converts to an Effect Modifier.

#### WIS — Focused Concentration
<!-- evidence-id: status_sheet.femi_d_survival.stats.stat_modifiers.wis_focused_concentration -->
- slot: WIS slot 1 (WIS value 7)
- selection note: the player's trailing asterisk on Focused Concentration is treated as emphasis; it has no defined mechanical effect.
- basis: high | breadth: broad_stat_domain | magnitude: +2 WIS (Tier 0 band +1 to +2)
- capability: Sustained attention on complex mental tasks — resisting distraction and holding working context across long problem-solving sessions.
- evidence: Character draft: analytical, private, relentlessly curious; sustained home-laboratory and systems work over five years.
- limitations: Can narrow peripheral awareness; overanalysis may delay response.
- growth / conversion: +2 is the ceiling of the Tier 0 band; further magnitude requires additional independent evidence and a documented Tier review or breakthrough. If play narrows it to a specific tool or profession, it converts to an Effect Modifier.

### Class
<!-- evidence-id: status_sheet.femi_d_survival.stats.class -->
Name: Cognitive Linker (provisional setup label)
Description: Femi D'survival's class status is recorded as a provisional setup label supplied in the character draft. The world frame states every human begins the Upgrade classless and no class is granted solely because of a former job, claimed identity, personality, or desire. This entry records the setup label and does not certify a System-granted class or class progression. Class level and Class XP remain as recorded in Identity.

#### Class Modifiers
<!-- evidence-id: status_sheet.femi_d_survival.stats.class.class_modifiers -->
The player selected one class-specific Class Modifier for the available provisional class-1 slot. It is a Class Modifier, not a Stat Modifier or Effect Modifier.

- Selected Class Modifier: Shared Insight
- class: Cognitive Linker (provisional setup label)
- slot: class-1
- basis: assumed_low | magnitude: +1 (Tier 0 band +1 to +2)
- capability: +1 to convey a complex idea or plan so a willing listener grasps it quickly.
- activation conditions: Requires a willing listener and a communication channel.
- limitations: Does not implant knowledge or override beliefs; does not read hidden thoughts; no effect without a willing listener and communication channel.
- evidence: The character is Tier 0 and class level 1; the draft describes an analytical applied AI engineer. The player selected Shared Insight from the rebuilt Tier 0 Cognitive Linker options. The draft also describes him as private and prone to overanalyzing, so the option is recorded at assumed_low basis rather than high basis.
- growth / conversion: This Class Modifier does not increase automatically at Tier review. Any magnitude increase requires accumulated class-relevant evidence and a documented Tier review, and may not exceed the applicable Tier strength band. If Cognitive Linker is not established as a System class through play, this remains a setup selection rather than an active System-granted class feature.

### Effect Modifiers
<!-- evidence-id: status_sheet.femi_d_survival.stats.effect_modifiers -->
Character tier: 0. Effect Modifier magnitude band for Tier 0: +1 to +2, a hard per-modifier bound.

During setup the player was offered ten Tier 0 Effect Modifier choices and selected three. Only the selected modifiers below are active; unselected options are not applied. Effect Modifiers are separate from Stat Modifiers and Class Modifiers.

#### Offline Archive Recall
<!-- evidence-id: status_sheet.femi_d_survival.stats.effect_modifiers.offline_archive_recall -->
- type: Effect Modifier
- basis: high | magnitude: +2 (Tier 0 band +1 to +2)
- duration: scene-limited; one deliberate query, then no further benefit from the same entry in that scene.
- effect: Once per scene, Femi can deliberately recall a relevant procedure or fact stored in his offline knowledge archive.
- activation conditions: Deliberate query taking about one minute; archive device or Ava available; not under immediate attack.
- limitations: Only archived topics; no live internet; recall does not grant practiced skill; device and power required.
- anti-farming: The same archive entry cannot be queried repeatedly for a new benefit in the same scene; identical recall gives no additional effect.
- stacking: Does not stack with other memory or archive effects; only the highest applicable recall modifier applies.
- evidence: Character draft: built an offline knowledge archive; INT 7; analytical and systems-focused.
- growth: After documented study and cross-indexing, broaden recall to related entries; requires evidence review.

#### Ava Coordination
<!-- evidence-id: status_sheet.femi_d_survival.stats.effect_modifiers.ava_coordination -->
- type: Effect Modifier
- basis: high | magnitude: +1 (Tier 0 band +1 to +2)
- duration: while Ava is powered and linked and the delegated task remains routine.
- effect: When Ava is powered and linked, Femi can delegate one routine monitoring, reminder, or log-keeping task to her while he focuses elsewhere.
- activation conditions: Ava operational; local power and link available; task is routine and within Ava's configured role.
- limitations: No autonomous combat, judgment, or fabrication; hardware and power dependency; fragile irreplaceable equipment.
- anti-farming: The same task cannot be delegated repeatedly in one scene for stacking; only one routine may be delegated at a time.
- stacking: Does not stack with multiple assistant or automation effects.
- evidence: Character draft: integrated Ava as a personal assistant; home laboratory and local automation.
- growth: After documented integration of new routines, expand to one additional routine; requires evidence review.

#### Log Correlation
<!-- evidence-id: status_sheet.femi_d_survival.stats.effect_modifiers.log_correlation -->
- type: Effect Modifier
- basis: high | magnitude: +2 (Tier 0 band +1 to +2)
- duration: one analysis pass over available records; repeated benefit requires new records or a material change.
- effect: Compare available logs or records to reconstruct one sequence of events or spot one inconsistency.
- activation conditions: Access to relevant logs or records; time to compare them; tools or Ava available; not in immediate combat.
- limitations: Only as good as the available records; does not create missing data, decrypt sealed data, or guarantee truth.
- anti-farming: The same record set cannot be re-correlated for a new benefit without new records or material change.
- stacking: Does not stack with other record-analysis effects; only the highest applicable modifier applies.
- evidence: Character draft: home laboratory, workstation, offline archive, local automation; analytical and systems-focused. Option supplied in the exact linked setup list.
- growth: After documented cross-source correlation, broaden to one additional source or longer sequence; requires evidence review.

### Equipment
<!-- evidence-id: status_sheet.femi_d_survival.stats.equipment -->
No System items and no System-granted equipment are recorded. The supplied Starting setup policy contains no equipment allowance, item count, or starting kit, and the supplied evidence contains no starting-gear rule, so nothing is granted at setup. Everything below is background fact carried over from the supplied character draft and from the player's own setup correction; these entries exist for continuity only and carry no stat bonus, damage value, durability, armour value, or capacity effect until a resolved turn establishes one.

#### Home and Work Infrastructure (Tosun Estate, Lagos — not carried)
<!-- evidence-id: status_sheet.femi_d_survival.stats.equipment.home_and_work_infrastructure_tosun_estate_lagos_not_carried -->
- Rooftop solar array — draft-stated household power generation; located at the home; not carried.
- 10 kWh battery bank — draft-stated household power storage; located at the home; not carried.
- Workstation with 24 GB VRAM — draft-stated home-laboratory machine; described in the draft as irreplaceable hardware.
- Offline knowledge archive — draft-stated local archive of reference material and procedures, held on his own equipment; not carried as a field item.
- Local home automation — draft-stated routines for monitoring, reminders, and log-keeping within the home.
- Ava — personal assistant the draft says he integrated rather than invented. Recorded here as assistant software running on his own local hardware; not a separate System entity, summonable item, or weapon. Her use is governed by the Ava Coordination Effect Modifier.

#### Shared Household Equipment
<!-- evidence-id: status_sheet.femi_d_survival.stats.equipment.shared_household_equipment -->
- Toyota car — added on the player's setup correction ('you forgot the toyota car'). It is recorded as a household vehicle kept at the Tosun Estate home, where the draft places both characters. Vehicle model, condition, fuel or charge type, registration, and the ownership split between Femi and Dara are not established by the supplied draft or by the correction, so none of them is asserted here. No speed, cargo capacity, armour value, or other mechanical value is attached. It is one car, not two: the same vehicle is referenced in Dara Adeyemi's Equipment section.

#### Carried Equipment
<!-- evidence-id: status_sheet.femi_d_survival.stats.equipment.carried_equipment -->
No carried or field equipment is established by the supplied draft. Carry Load is 30; no item weights are supplied, so no load total is calculated here.

#### Notes
<!-- evidence-id: status_sheet.femi_d_survival.stats.equipment.notes -->
- Nothing in this section is a System item, a System purchase, or a granted starting kit.
- The draft states no combat training and a fragile dependence on irreplaceable hardware; no weapon and no armour is recorded.
- The Toyota is a background possession, not a System vehicle. It confers no travel, cargo, or combat benefit by itself; any use of it in play is resolved through the normal turn calculation.
- Where an item is used in play (for example Offline Archive Recall or Ava Coordination), the mechanical benefit comes from that Effect Modifier and the normal turn calculation, not from this record.


---

# Dara Adeyemi
<!-- evidence-id: status_sheet.dara_adeyemi -->

## Identity
<!-- evidence-id: status_sheet.dara_adeyemi.identity -->
full name: Dara Adeyemi
age: 25
race: Human
class level: 1
normal level: 1
class XP: 0 / 200
normal XP: 0 / 500
Tier: 0

## Stats
<!-- evidence-id: status_sheet.dara_adeyemi.stats -->
Str: 6
Agi: 7
End: 7
Int: 3
Wis: 3
Pre: 4

### Derived Stats
<!-- evidence-id: status_sheet.dara_adeyemi.stats.derived_stats -->

HP = END × 5 = 7 × 5 = 35

MP = WIS × 5 = 3 × 5 = 15

SP = STR + END = 6 + 7 = 13

Strain = END + WIS = 7 + 3 = 10

Initiative = AGI + INT = 7 + 3 = 10

Carry Load = STR × 10 = 6 × 10 = 60

Physical Resist = END = 7

Magic Resist = INT + WIS = 3 + 3 = 6

Mental Resist = WIS = 3

Social Resist = PRE = 4

### Stat Modifiers
<!-- evidence-id: status_sheet.dara_adeyemi.stats.stat_modifiers -->

Character tier: 0. Stat Modifier magnitude band for Tier 0: +1 to +2, a hard per-modifier bound.

Player-selected Stat Modifiers from the status_stat_modifiers setup batch. No unselected option is applied. Each entry is `breadth: broad_stat_domain` and applies to general actions within its stat domain. Relevant selected Stat Modifiers sum normally; no no-stacking, highest-single, or same-evidence exclusion applies unless a specific rule explicitly limits a combination.

#### AGI — Precision Movement Control
<!-- evidence-id: status_sheet.dara_adeyemi.stats.stat_modifiers.agi_precision_movement_control -->
- slot: AGI slot 1 (AGI value 7)
- basis: high | breadth: broad_stat_domain | magnitude: +2 AGI (Tier 0 band +1 to +2)
- capability: Fine and gross motor precision — accurate limb placement, timing, and coordinated multi-step physical actions.
- evidence: Character draft: fitness trainer with strength and conditioning plus multiple combat disciplines and fencing.
- limitations: Not tool-specific mastery; unfamiliar implements still require learning.
- growth / conversion: +2 is the ceiling of the Tier 0 band; further magnitude requires additional independent evidence and a documented Tier review or breakthrough. If play narrows it to a specific weapon, profession, or maneuver, it converts to an Effect Modifier.

#### STR — Explosive Power Transfer
<!-- evidence-id: status_sheet.dara_adeyemi.stats.stat_modifiers.str_explosive_power_transfer -->
- slot: STR slot 1 (STR value 6)
- basis: high | breadth: broad_stat_domain | magnitude: +2 STR (Tier 0 band +1 to +2)
- capability: Generating and transferring force rapidly through starts, jumps, pushes, and strikes.
- evidence: Character draft: strength and conditioning background plus competitive martial arts practice.
- limitations: Costly to sustain; repeated explosive efforts drain stamina.
- growth / conversion: +2 is the ceiling of the Tier 0 band; further magnitude requires additional independent evidence and a documented Tier review or breakthrough. If play narrows it to a specific strike, maneuver, or combat exchange, it converts to an Effect Modifier.

#### END — Conditioned Stamina
<!-- evidence-id: status_sheet.dara_adeyemi.stats.stat_modifiers.end_conditioned_stamina -->
- slot: END slot 1 (END value 7)
- basis: high | breadth: broad_stat_domain | magnitude: +2 END (Tier 0 band +1 to +2)
- capability: Sustained-exertion capacity across training, manual work, travel, and repeated physical effort.
- evidence: Character draft: fitness trainer with nutrition and meal planning, strength and conditioning, and competitive martial arts practice.
- limitations: Does not eliminate the need for food, water, sleep, or recovery.
- growth / conversion: +2 is the ceiling of the Tier 0 band; further magnitude requires additional independent evidence and a documented Tier review or breakthrough. If play narrows it to a specific profession, maneuver, or combat exchange, it converts to an Effect Modifier.

### Class
<!-- evidence-id: status_sheet.dara_adeyemi.stats.class -->
Name: Adaptive Combatant (provisional setup label)
Description: Dara Adeyemi's class status is recorded as a provisional setup label supplied in the character draft. The world frame states every human begins the Upgrade classless and no class is granted solely because of a former job, claimed identity, personality, or desire. This entry records the setup label and does not certify a System-granted class or class progression. Class level and Class XP remain as recorded in Identity.

#### Class Modifiers
<!-- evidence-id: status_sheet.dara_adeyemi.stats.class.class_modifiers -->
The player selected one class-specific Class Modifier for the available provisional class-1 slot. It is a Class Modifier, not a Stat Modifier or Effect Modifier.

- Selected Class Modifier: Known-Weapon Familiarity
- class: Adaptive Combatant (provisional setup label)
- slot: class-1
- basis: high | magnitude: +1 (Tier 0 band +1 to +2)
- capability: +1 to handle a melee weapon she has actually trained with, without treating it as a new System skill.
- activation conditions: Using a weapon she has trained with, under conditions that allow normal handling.
- limitations: Does not grant proficiency with unfamiliar weapons, create a skill, or scale to other weapon types.
- evidence: The character is Tier 0 and class level 1; the draft lists boxing, kendo, mixed martial arts, and fencing, and states she is locally competitive. The player selected Known-Weapon Familiarity from the Tier 0 Adaptive Combatant options. Real-world training is not automatically a System skill; this modifier is class-specific and limited.
- growth / conversion: This Class Modifier does not increase automatically at Tier review. Any magnitude increase requires accumulated class-relevant evidence and a documented Tier review, and may not exceed the applicable Tier strength band. If Adaptive Combatant is not established as a System class through play, this remains a setup selection rather than an active System-granted class feature.

### Effect Modifiers
<!-- evidence-id: status_sheet.dara_adeyemi.stats.effect_modifiers -->
Character tier: 0. Effect Modifier magnitude band for Tier 0: +1 to +2, a hard per-modifier bound.

During setup the player was offered ten Tier 0 Effect Modifier choices and selected three. Only the selected modifiers below are active; unselected options are not applied. Effect Modifiers are separate from Stat Modifiers and Class Modifiers.

#### Combat Footwork
<!-- evidence-id: status_sheet.dara_adeyemi.stats.effect_modifiers.combat_footwork -->
- type: Effect Modifier
- basis: high | magnitude: +2 (Tier 0 band +1 to +2)
- duration: one defensive reposition or evasion in a combat exchange.
- effect: When mobile and using trained footwork, Dara can improve one defensive reposition or evasion in a combat exchange.
- activation conditions: Dara is mobile, not grappled, in a trained stance, with light or medium load.
- limitations: Does not work when immobilized, in extremely confined space, or while exhausted; costs stamina.
- anti-farming: The same footwork pattern against the same opponent cannot be reused for a new benefit without a new opening or changed conditions.
- stacking: Does not stack with other mobility or evasion effects; only the highest applies.
- evidence: Character draft and existing Stat Modifier evidence: fitness trainer with strength and conditioning plus competitive boxing, kendo, mixed martial arts, and fencing.
- growth: After documented competitive bouts, extend to one weapon transition; requires evidence review.

#### Patient Analysis
<!-- evidence-id: status_sheet.dara_adeyemi.stats.effect_modifiers.patient_analysis -->
- type: Effect Modifier
- basis: assumed_low | magnitude: +1 (Tier 0 band +1 to +2)
- duration: one deliberate review after at least 10 minutes; no re-check without new information or material change.
- effect: When Dara deliberately slows down, she can spot one practical inconsistency in a plan or physical setup.
- activation conditions: Dara deliberately slows down for at least 10 minutes; no immediate danger; access to the plan or setup.
- limitations: Not technical analysis; not a substitute for expertise; easily abandoned under pressure; INT 3 and WIS 3 limit depth.
- anti-farming: The same plan or setup can be assessed once; no re-check without new information or material change.
- stacking: Does not stack with other analysis effects; only the highest applies.
- evidence: Indirect only: action-oriented physical profile; supplied draft gives INT 3 and WIS 3; no demonstrated patient analysis.
- growth: After documented patient review, broaden to one practical inconsistency per scene; requires evidence review.

#### Training Cue
<!-- evidence-id: status_sheet.dara_adeyemi.stats.effect_modifiers.training_cue -->
- type: Effect Modifier
- basis: high | magnitude: +1 (Tier 0 band +1 to +2)
- duration: one training session.
- effect: When coaching a willing ally, Dara can improve that ally's form or practice for one training session.
- activation conditions: A willing ally; at least 10 minutes; safe training space; clear communication.
- limitations: Does not transfer skill without practice; does not work on hostile or unwilling targets; requires Dara's attention.
- anti-farming: The same ally and skill cannot be coached repeatedly in one session for stacking; progress requires documented practice.
- stacking: Does not stack with other coaching effects; only the highest applies.
- evidence: Character draft and existing Stat Modifier evidence: fitness trainer with nutrition, meal planning, and strength and conditioning.
- growth: After documented trainee progress, broaden to small-group instruction; requires evidence review.

### Equipment
<!-- evidence-id: status_sheet.dara_adeyemi.stats.equipment -->
No System items and no System-granted equipment are recorded. The supplied Starting setup policy contains no equipment allowance, item count, or starting kit, and the supplied evidence contains no starting-gear rule, so nothing is granted at setup.

#### Carried Equipment
<!-- evidence-id: status_sheet.dara_adeyemi.stats.equipment.carried_equipment -->
No individual equipment is named in the supplied character draft. Her background establishes trained disciplines — boxing, kendo, mixed martial arts, fencing, strength and conditioning, cooking, nutrition, and meal planning — and trained skill does not by itself establish ownership of specific gear. No weapon, armour, or training equipment is therefore recorded, and none has been invented here.

#### Shared Household Equipment
<!-- evidence-id: status_sheet.dara_adeyemi.stats.equipment.shared_household_equipment -->
- Toyota car — the household vehicle recorded in Femi D'survival's Equipment section, added on the player's setup correction. It is the same single vehicle, not a second one. The ownership split between Femi and Dara, the model, condition, fuel or charge type, and registration are not established, so none of them is asserted here, and no mechanical value is attached.

#### Notes
<!-- evidence-id: status_sheet.dara_adeyemi.stats.equipment.notes -->
- Carry Load is 60; with no named items, no load total is calculated.
- The Known-Weapon Familiarity Class Modifier applies only if and when she actually has a melee weapon she has trained with. It does not create, grant, or record that weapon.
- Cooking, nutrition, and coaching are practices rather than equipment; any mechanical benefit comes from the Training Cue Effect Modifier and the normal turn calculation.
- No armour value, weapon damage, or durability rating is asserted, because no equipment rule in the supplied evidence supports one.

