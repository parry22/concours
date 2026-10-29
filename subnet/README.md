# Concours on Bittensor

Concours runs its own subnet. Outside solvers (miners) submit fraud solvers on chain. Concours, as the
subnet's validator, measures each one exactly like a local attempt: in the player container, against the referee,
on the private holdout, and through the five promotion gates. The miner whose code becomes the active version gets
all the weight (winner takes all). While no miner has won, the weight goes to the subnet owner's uid.

```
miner ──signed upload──▶ validator intake (:8091) ──▶ Concours API ──▶ arena round (Docker) ──▶ gates ──▶ new version
  └──commitment "concours:<sha256>" on chain ◀── validator reads commitments, sets weights ◀── winner from Concours
```

- The chain records who submitted which code and when: a commitment is the sha256 of the uploaded `submission.py`.
  The validator only scores code whose hash a registered hotkey committed. If two hotkeys commit the same hash, the
  earlier commitment gets it.
- The private holdout never leaves the Concours server. Neither miners nor this validator process see it.
- A submission is one `submission.py` with a `Solver` class, the same contract as `backend/solvers/*/submission.py`.
  The limit is 200 KB. It runs with no network except the referee's, 2 CPUs and 2 GB of memory.

Files: `concours_subnet/miner.py`, `concours_subnet/validator.py`, `concours_subnet/common.py`,
`scripts/localnet_setup.py`. Backend side: `backend/app/chain.py`, with the routes `GET /projects/{id}/chain`,
`PUT …/chain/state` and `POST …/chain/submissions`.

## Install

```bash
cd subnet && uv sync && source .venv/bin/activate   # bittensor 11 SDK + btcli, separate from the backend venv
```

## Testnet runbook (buildathon demo)

You run every step that creates keys or spends TAO. Mnemonics print once. Write them down offline and never
paste them into chat or a file in the repo.

**1. Wallets** (in your own terminal):

```bash
btcli -n test wallet create -w concours-owner -H validator
btcli -n test wallet create -w concours-miner -H m1
btcli -n test wallet new-hotkey -w concours-miner -H m2
```

**2. Test TAO.** There is no faucet. Ask in the Bittensor Discord for testnet TAO, and send it to the
`concours-owner` coldkey (`btcli wallet list` shows the address). Budget: the subnet burn (1 τ when checked on
2026-10-28; run `btcli -n test subnets list` or `btcli query --help` for the current cost), a few τ for hotkey
registrations, and stake for the validator. 10 τ is comfortable. Give each miner coldkey about 1 τ:
`btcli -n test tx transfer --dest <miner coldkey> --amount-tao 1 -w concours-owner`.

**3. Subnet, registrations, stake:**

```bash
btcli -n test tx register-subnet -w concours-owner -H validator          # note the new netuid it prints
btcli -n test tx start-call --netuid <N> -w concours-owner               # may need to wait some blocks after creation
btcli -n test tx burned-register --netuid <N> -w concours-miner -H m1
btcli -n test tx burned-register --netuid <N> -w concours-miner -H m2
btcli -n test tx add-stake --netuid <N> --hotkey concours-owner/validator --amount-tao 2 -w concours-owner
```

Add `--dry-run` to any `tx` command to preview the cost first.

**4. Validator.** Create an API key in Concours (Account → API keys), then:

```bash
CONCOURS_API_KEY=ck_... .venv/bin/concours-validator --network test --netuid <N> \
  --wallet concours-owner --hotkey validator --project <project id> --api http://127.0.0.1:8000
```

The Improve tab of that project now shows "Bittensor testnet · netuid N" and an "On Bittensor" card. Miners need
to reach the intake on port 8091: on a laptop, expose it with a tunnel and give miners that URL.

**5. Miners:**

```bash
.venv/bin/concours-miner submit path/to/submission.py --network test --netuid <N> \
  --wallet concours-miner --hotkey m2 --validator http://<validator host>:8091
.venv/bin/concours-miner status --network test --netuid <N> --wallet concours-miner --hotkey m2
```

### The demo project

`scripts/seed.py --only=bittensor` creates "Card fraud on Bittensor". It runs version 1, then the clock moves into
the new card-testing pattern and the project is left slipping (catching about 20% less). A miner submitting the
velocity solver (`backend/solvers/lgbm_velocity/submission.py`, or your own) fixes it. Verified on a local chain on
2026-10-28: the miner's attempt scored $6,543/day against the champion's $4,685, passed all five gates and became v2,
credited to its uid.

## Local chain (no TAO)

```bash
docker run -d --name concours-localnet -p 9944:9944 -p 9945:9945 ghcr.io/opentensor/subtensor-localnet:devnet-ready
.venv/bin/python scripts/localnet_setup.py --wallet-path /tmp/concours-localnet-wallets   # throwaway wallets, funded from //Alice
```

Then use `--network local --wallet-path /tmp/concours-localnet-wallets` with the commands above (wallet `owner`,
hotkey `validator`; wallet `miner`, hotkeys `m1`, `m2`).

Known limit: the `devnet-ready` image pulled on 2026-10-28 (built 2026-07-01) is older than the SDK. Registration
falls back to raw calls, but weights cannot be set there, because commit-reveal is on and the owner's switch-off
call hangs on that runtime. Testnet runs the current runtime, where `bt.set_weights` handles commit-reveal itself.
Weights on testnet are therefore not verified yet.
