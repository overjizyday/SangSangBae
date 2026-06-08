# Game Result Rules

This project uses two rule flags for simulated baseball results.

- `D`: Draws are allowed after regulation nine innings.
- `L`: Draws are not allowed. The game continues into extra innings until the relevant score is no longer tied. Random tiebreaker runs are not allowed.
- `E`: Walk-off ending is enabled. If the home side is already ahead before the bottom of the ninth, or moves ahead during the bottom of the ninth or later, the game ends immediately.
- `N`: Walk-off ending is disabled. The home side always completes the bottom half of the inning, including the bottom of the ninth.

Applied rules:

- League: `DE`
- Local cup regional qualifiers and group qualifiers: `DE`
- Local cup with 14 teams: no group stage is played. The eight-team main bracket starts immediately and uses normal two-leg tournament rules.
- Local cup with a group stage, such as 30 or more teams: 15 qualifiers plus the previous champion form four groups of four. The first main-round games after the group stage are single-leg `DE` games. The group winner side is the home team and advances on a draw.
  - A/B side pairings: `A2 at B1`, `B2 at A1`.
  - C/D side pairings: `C2 at D1`, `D2 at C1`.
  - Additional group pairs follow the same pattern.
- Local cup tournament matches other than that first post-group main-round game:
  - Leg 1: `DN`
  - Leg 2: aggregate `LE`
- ACL group stage: `DE`
- ACL and local cup PO: `LE`
- All other tournament matches:
  - Leg 1: `DN`
  - Leg 2: aggregate `LE`

For aggregate `LE`, the bottom-half walk-off check is based on the two-leg aggregate, not just the current leg score.
