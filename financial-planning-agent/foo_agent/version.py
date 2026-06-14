"""Single source of truth for all version + determinism identifiers.

Every Result embeds these so an output can always be reproduced from a known
engine + ruleset + assumptions combination. The loader fails closed if the
ruleset on disk declares a schema version the engine does not understand.
"""
from __future__ import annotations

# Engine code version (bump on behavioural change to the decision path).
__version__ = "0.1.0"

# The rule/profile/recommendation schema generation the engine speaks. A ruleset
# whose manifest declares a different schema version is refused at load time.
RULESET_SCHEMA_VERSION = "1.0.0"

# Default Monte Carlo seed. Callers may override, but the value used is always
# recorded in the Result so the run is reproducible.
DEFAULT_MC_SEED = 424242

# Default number of Monte Carlo trials.
DEFAULT_MC_TRIALS = 10000
