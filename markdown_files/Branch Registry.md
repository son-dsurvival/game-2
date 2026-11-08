# Branch Registry

This document tracks branch discovery and activation for the game runtime. `candidate` means branch discovery found relevant lore, log, chat, cache, or state evidence; it is recorded but not routed. A branch specialist and branch template are used only when the status is `unlocked`.

## Business
status: candidate
specialist: business
template: business.md
activation tags: activity.business
discovery status: candidate
discovery sources: markdown_files/game rules (1).md, markdown_files/🌍 CORE WORLD FRAME (REFINED).md, brain/state/session_runtime.json, runtime.evidence_bundle, runtime.evidence_bundle.conversation_history
reason: trade, markets, contracts, and enterprise

## Alchemy
status: candidate
specialist: alchemy
template: alchemy.md
activation tags: activity.alchemy
discovery status: lore_candidate
discovery sources: markdown_files/game rules (1).md, markdown_files/🌍 CORE WORLD FRAME (REFINED).md, runtime.evidence_bundle
reason: alchemy processes, recipes, and reagents

## Politics
status: candidate
specialist: politics
template: politics.md
activation tags: activity.politics, context.factional
discovery status: candidate
discovery sources: markdown_files/game rules (1).md, markdown_files/🌍 CORE WORLD FRAME (REFINED).md, brain/state/session_runtime.json, runtime.evidence_bundle, runtime.evidence_bundle.player_input, runtime.evidence_bundle.conversation_history
reason: factions, offices, diplomacy, and political power

## Class
status: candidate
specialist: class
template: class.md
activation tags: context.class_system
discovery status: candidate
discovery sources: markdown_files/game rules (1).md, markdown_files/TERMS_AND_NOMENCLATURE.md, markdown_files/🌍 CORE WORLD FRAME (REFINED).md, brain/state/session_runtime.json, runtime.evidence_bundle, runtime.evidence_bundle.player_input, runtime.evidence_bundle.conversation_history
reason: class choice and class progression

## Relay
status: candidate
specialist: relay
template: relay.md
activation tags: context.relay_system
discovery status: lore_candidate
discovery sources: markdown_files/game rules (1).md, runtime.evidence_bundle
reason: relay and linked-network mechanics

## World
status: candidate
specialist: world
template: none
activation tags: activity.exploration, mechanic.world_event
discovery status: candidate
discovery sources: markdown_files/game rules (1).md, markdown_files/TERMS_AND_NOMENCLATURE.md, markdown_files/🌍 CORE WORLD FRAME (REFINED).md, brain/state/session_runtime.json, runtime.evidence_bundle
reason: scheduled world events and world-state changes

## Consequences
status: candidate
specialist: consequences
template: none
activation tags: stakes.irreversible, stakes.contested
discovery status: candidate
discovery sources: markdown_files/game rules (1).md, runtime.evidence_bundle, runtime.evidence_bundle.conversation_history
reason: persistent and irreversible consequences

## Dungeon Ecology
status: candidate
specialist: dungeon_ecology
template: none
activation tags: activity.exploration, context.environmental
discovery status: lore_candidate
discovery sources: markdown_files/🌍 CORE WORLD FRAME (REFINED).md, runtime.evidence_bundle
reason: dungeons, production pressure, monster populations, and tides

## Peoples
status: candidate
specialist: peoples
template: none
activation tags: context.factional, context.social
discovery status: candidate
discovery sources: markdown_files/🌍 CORE WORLD FRAME (REFINED).md, brain/state/session_runtime.json, runtime.evidence_bundle, runtime.evidence_bundle.conversation_history
reason: peoples, species recognition, and inter-peoples relations

## Civilization
status: candidate
specialist: civilization
template: none
activation tags: context.civilization, activity.base_development
discovery status: lore_candidate
discovery sources: markdown_files/game rules (1).md, markdown_files/🌍 CORE WORLD FRAME (REFINED).md, runtime.evidence_bundle
reason: Bases and civilization hierarchy

## Religion
status: candidate
specialist: religion
template: none
activation tags: context.religious, context.tier6
discovery status: lore_candidate
discovery sources: markdown_files/🌍 CORE WORLD FRAME (REFINED).md, runtime.evidence_bundle
reason: Tier-6 entities, religions, blessings, and champions

## Technology
status: candidate
specialist: technology
template: none
activation tags: activity.engineering, context.technology
discovery status: candidate
discovery sources: markdown_files/🌍 CORE WORLD FRAME (REFINED).md, runtime.evidence_bundle, runtime.evidence_bundle.conversation_history
reason: technology, engineering, and mana integration

## Knowledge
status: candidate
specialist: knowledge
template: none
activation tags: activity.study, context.knowledge
discovery status: candidate
discovery sources: markdown_files/🌍 CORE WORLD FRAME (REFINED).md, brain/state/session_runtime.json, runtime.evidence_bundle, runtime.evidence_bundle.conversation_history
reason: knowledge markets, study, and instructional institutions

## Unlock Rules

A branch becomes `unlocked` only when a resolved turn provides evidence that the branch has been established. A player request or a specialist proposal alone creates a candidate; it does not unlock the branch.
