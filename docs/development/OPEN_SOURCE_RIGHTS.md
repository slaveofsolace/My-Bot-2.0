# Open-source ownership and protected recognition resources

This is an engineering boundary, not legal advice.

## What publishing source does and does not do

Publishing source code does **not** make its author lose copyright. Copyright ownership and the permissions granted by a licence are separate. A contributor can keep copyright while granting everyone broad reuse rights.

The MIT licence permits use, copying, modification, merging, publication, distribution, sublicensing and sale. Its operative attribution condition is that the copyright and permission notice remain in copies or substantial portions. MIT does not itself require a visible backlink on every screen, although a clear project link is good attribution and this project preserves one.

The MyBot.run lineage in this repository is different: its AutoIt source is GPLv3-derived, while some inherited compiled recognition components have separate, unclear or restrictive terms. A repository-level GPL label or possession of a binary does not prove that every binary or encrypted data file may be modified or redistributed.

## Encrypted XML and ImgLoc

The project will not decrypt protected XML, patch identity checks, decompile a proprietary component, or use another executable as a decoy. Those approaches would not create a maintainable open engine and could cross legal and security boundaries.

A rights-safe replacement is possible, but it is a clean-room subsystem project:

1. document the public input/output behavior required by each recognition call;
2. implement an open matcher behind the existing AutoIt wrapper contract;
3. create or obtain separately licensed templates and OCR fixtures;
4. test coordinates, confidence, error semantics, memory ownership and interruption behavior;
5. replay approved current-client fixtures and then run controlled live checks;
6. remove the inherited binary only after feature parity and release review.

Until that work is complete, local use of the inherited pinned component and public redistribution are separate decisions. Public redistribution remains on hold unless written permission is obtained or the component is replaced.

## MyBotPy reference disposition

**Decision: REFERENCE ONLY.** The reviewed source is [`evgmalkov/mybot-py`](https://github.com/evgmalkov/mybot-py), pinned in `upstreams.lock.json` at commit `ae24b6d99d522730ab2822282563af764dfa9f5a`. Its root `LICENSE` is MIT, copyright 2026 evgmalkov.

The useful general principles are exact emulator-instance selection, emulator-compatible ADB selection, bounded capture, one cached frame for several recognizers, batched input, interruption-aware attacks and data-driven gameplay policies. No MyBotPy executable, template, account data or dependency is shipped here, and no substantial source was copied in this pass. If a later change copies MIT-covered source, its copyright and permission notice must travel with that copy and the change must identify the adapted files.
