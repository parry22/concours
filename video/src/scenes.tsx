import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { at, C, clamp01, EASE, GRAD, GRAD_X, keys, OUT, prog, SANS, SceneInfo, Sfx } from "./lib";
import { Badge, Button, CheckBox, CountUp, Enter, Hand, Mono, Row, Spinner, Stage, Step, Surface, Typing } from "./ui/Kit";
import { Logo } from "./ui/Logo";
import { Line, wordsOf } from "./ui/Text";

type P = { scene: SceneInfo };

const Label: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => (
  <div style={{ fontSize: 19, letterSpacing: 1.6, textTransform: "uppercase", color: C.muted, fontWeight: 500, ...style }}>{children}</div>
);
const Title: React.FC<{ children: React.ReactNode; sub?: React.ReactNode; right?: React.ReactNode }> = ({ children, sub, right }) => (
  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 24 }}>
    <div>
      <div style={{ fontSize: 38, fontWeight: 600, letterSpacing: -1 }}>{children}</div>
      {sub && <div style={{ fontSize: 23, color: C.subtle, marginTop: 8 }}>{sub}</div>}
    </div>
    {right}
  </div>
);
const SampleNote: React.FC = () => <div style={{ fontSize: 18, color: C.muted, marginTop: 22 }}>Sample project · simulated card payments</div>;

// Absolute box on the 1920x1080 stage.
const Box: React.FC<{ x: number; y: number; w: number; children: React.ReactNode }> = ({ x, y, w, children }) => (
  <div style={{ position: "absolute", left: x, top: y, width: w, fontFamily: SANS, color: C.fg }}>{children}</div>
);

// ---------- opening: type on white ----------

// Each line is fully gone before the next one starts: a quick exit, and the next line's words a few frames later.
const EXIT = 9;
const later = (ws: { w: string; at: number }[], d: number) => ws.map((w) => ({ ...w, at: w.at + d }));

export const Hook: React.FC<P> = ({ scene }) => <Line words={wordsOf(scene, 0)} size={104} accent={["still."]} exit={scene.frames - 12} exitDur={EXIT} />;

export const Problem: React.FC<P> = ({ scene }) => (
  <>
    <Line words={later(wordsOf(scene, 0), 4)} size={92} accent={["learned."]} exit={at(scene, 1) - 11} exitDur={EXIT} />
    <Line words={later(wordsOf(scene, 1), 3)} size={92} accent={["black", "boxes."]} exit={at(scene, 2) - 11} exitDur={EXIT} />
    <Line words={later(wordsOf(scene, 2), 3)} size={92} accent={["months."]} exit={scene.frames - 12} exitDur={EXIT} />
  </>
);

export const Intro: React.FC<P> = ({ scene }) => {
  const f = useCurrentFrame();
  const name = at(scene, 0, "Concours");
  const p = prog(f, name - 14, name + 14, OUT);
  const split = keys(f, [[name - 4, 0], [name + 16, 2.4], [name + 40, 1.3]]);
  const up = keys(f, [[at(scene, 1) - 6, 0], [at(scene, 1) + 14, 1]]);
  return (
    <>
      <div style={{ position: "absolute", left: 960 - 105, top: 250 - up * 36, opacity: p, filter: `blur(${(1 - p) * 10}px)`, transform: `scale(${0.88 + 0.12 * p})` }}>
        <Logo size={210} split={split} glow={0.6} />
      </div>
      <Line words={[{ w: "Concours", at: name }]} size={140} weight={600} y={590 - up * 36} />
      <Line words={wordsOf(scene, 1)} size={48} color={C.subtle} accent={["keep", "up"]} y={700 - up * 10} />
      <Sfx at={name - 2} name="shimmer" volume={0.22} />
    </>
  );
};

// ---------- product ----------

export const Upload: React.FC<P> = ({ scene }) => {
  const f = useCurrentFrame();
  const drop = scene.voiceAt + 20;
  const t = prog(f, scene.voiceAt, drop, EASE);
  const dropped = f >= drop;
  const fill = prog(f, drop, drop + 26, EASE);
  return (
    <Stage cam={[{ f: 0, z: 1.45, y: 560, x: 900 }, { f: drop + 6, z: 1.22, y: 520 }, { f: scene.frames, z: 1.16, y: 520 }]}>
      <Box x={410} y={250} w={1100}>
        <Enter at={0}>
          <Surface style={{ padding: 40 }}>
            <Title sub="A CSV of payments. The raw upload is deleted once columns are confirmed.">Your transactions</Title>
            <div style={{ marginTop: 30, height: 250, borderRadius: 18, border: `2px dashed ${dropped ? C.violet : "#d4d4d8"}`, background: dropped ? "#faf8ff" : "#fcfcfc",
              display: "flex", alignItems: "center", justifyContent: "center", padding: "0 34px" }}>
              {!dropped && <div style={{ fontSize: 26, color: C.muted }}>Drop your CSV here</div>}
              {dropped && (
                <div style={{ width: "100%" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
                    <div style={{ width: 40, height: 48, borderRadius: 9, background: GRAD }} />
                    <Mono style={{ fontSize: 28 }}>transactions.csv</Mono>
                    <div style={{ flex: 1 }} />
                    <span style={{ fontSize: 26, color: C.subtle }}><CountUp to={1762489} at={drop + 2} dur={26} prefix="" /> payments</span>
                  </div>
                  <div style={{ marginTop: 22, height: 10, borderRadius: 9, background: C.row, overflow: "hidden" }}>
                    <div style={{ width: `${fill * 100}%`, height: "100%", background: GRAD_X }} />
                  </div>
                  <div style={{ marginTop: 18, display: "flex", alignItems: "center", gap: 12, opacity: prog(f, drop + 26, drop + 36), fontSize: 23, color: C.subtle }}>
                    <CheckBox at={drop + 26} size={24} /> Columns matched: transaction, time, amount, customer, terminal, fraud label
                  </div>
                </div>
              )}
            </div>
          </Surface>
        </Enter>
      </Box>
      {!dropped && (
        <div style={{ position: "absolute", left: 1500 + (760 - 1500) * t, top: 120 + (640 - 120) * t, transform: `rotate(${(1 - t) * 6}deg)` }}>
          <Row style={{ gap: 14, padding: "14px 20px", background: "#fff", border: `1px solid ${C.border}`, boxShadow: "0 20px 40px -12px rgba(0,0,0,0.25)" }}>
            <div style={{ width: 30, height: 36, borderRadius: 7, background: GRAD }} />
            <Mono style={{ fontSize: 24 }}>transactions.csv</Mono>
          </Row>
        </div>
      )}
      <Hand show={0} hide={drop + 14} path={[{ f: 0, x: 1560, y: 150 }, { f: drop, x: 820, y: 670 }, { f: drop + 14, x: 860, y: 700 }]} clicks={[drop]} />
      <Sfx at={drop} name="tick" volume={0.4} />
      <Sfx at={0} name="whoosh" volume={0.12} />
      <Sfx at={drop + 26} name="pop" volume={0.18} />
    </Stage>
  );
};

// Questions: the first answer is typed and sent, then the other two land and the settings fill in.
const QA = [
  { q: "How many cases can your team review per day?", a: "200 cases a day" },
  { q: "What does one review cost, and is there a fee on a missed fraud?", a: "About 10 per review, no extra fee" },
  { q: "How long until fraud is usually confirmed?", a: "Usually about 30 days" },
];
export const Questions: React.FC<P> = ({ scene }) => {
  const f = useCurrentFrame();
  const typeAt = scene.voiceAt + 2;
  const send = typeAt + 16;
  const times = [-99, send + 2, send + 12, send + 18, send + 28, send + 34];
  const msgs = QA.flatMap((m) => [{ t: m.q, me: false }, { t: m.a, me: true }]);
  const H = [86, 66, 86, 66, 86, 66];
  const shown = msgs.map((_, i) => prog(f, times[i], times[i] + 10, EASE));
  const stackH = shown.reduce((s, p, i) => s + (H[i] + 14) * p, 0);
  const settings = [
    { k: "Cases reviewed per day", v: "200", t: send + 4 },
    { k: "Cost of one review", v: "$10.00", t: send + 20 },
    { k: "Extra cost of a missed fraud", v: "$0.00", t: send + 22 },
    { k: "Days until fraud is confirmed", v: "30", t: send + 36 },
  ];
  const step = f < send + 12 ? 1 : f < send + 28 ? 2 : 3;
  let y = 0;
  return (
    <Stage cam={[{ f: 0, z: 1.3, x: 700, y: 770 }, { f: send + 4, z: 1.3, x: 700, y: 760 }, { f: send + 22, z: 1.04, x: 960, y: 540 }, { f: scene.frames, z: 1.08 }]}>
      <Box x={180} y={160} w={1000}>
        <Enter at={0}>
          <Surface style={{ padding: 36, height: 760, display: "flex", flexDirection: "column" }}>
            <Title right={<Badge tone="neutral" dot={false}>{step} of 3</Badge>}>Three questions</Title>
            <div style={{ fontSize: 22, color: C.subtle, marginTop: 6 }}>About your team, not about models.</div>
            <div style={{ flex: 1, position: "relative", overflow: "hidden", marginTop: 20 }}>
              {/* Messages stack from the bottom; each new one pushes the rest up. */}
              <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: stackH }}>
                {msgs.map((m, i) => {
                  if (shown[i] <= 0) return null;
                  const top = y;
                  y += (H[i] + 14) * shown[i];
                  return (
                    <div key={i} style={{ position: "absolute", top, left: 0, right: 0, display: "flex", justifyContent: m.me ? "flex-end" : "flex-start", gap: 14,
                      opacity: shown[i], transform: `translateY(${(1 - shown[i]) * 16}px)` }}>
                      {!m.me && <Logo size={42} />}
                      <div style={{ background: m.me ? C.okBg : C.row, color: m.me ? C.ink : C.fg, borderRadius: 16, padding: "16px 22px", fontSize: 25, maxWidth: 720, fontWeight: m.me ? 500 : 400 }}>{m.t}</div>
                    </div>
                  );
                })}
              </div>
            </div>
            <div style={{ marginTop: 20, border: `1.5px solid ${f < send ? C.violet : C.border}`, borderRadius: 16, padding: "18px 20px 18px 24px", display: "flex", alignItems: "center", gap: 16,
              boxShadow: f < send ? "0 0 0 4px rgba(139,92,246,0.12)" : "none" }}>
              <div style={{ flex: 1, fontSize: 26, color: C.fg, minHeight: 34 }}>{f < send ? <Typing text="200 cases a day" at={typeAt} cps={1.2} /> : <span style={{ color: C.muted }}>Type an answer</span>}</div>
              <Button press={send} size={22}>Send</Button>
            </div>
          </Surface>
        </Enter>
      </Box>
      <Box x={1230} y={160} w={520}>
        <Enter at={send + 2}>
          <Surface style={{ padding: 34 }}>
            <div style={{ fontSize: 28, fontWeight: 600 }}>What we will use</div>
            {settings.map((s, i) => {
              const p = prog(f, s.t, s.t + 12);
              return (
                <div key={s.k} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", height: 74, borderTop: i ? `1px solid ${C.border}` : "none", marginTop: i ? 0 : 16 }}>
                  <span style={{ fontSize: 22, color: p > 0.5 ? C.fg : C.muted }}>{s.k}</span>
                  <Mono style={{ fontSize: 25, opacity: p, transform: `translateY(${(1 - p) * 8}px)` }}>{s.v}</Mono>
                </div>
              );
            })}
          </Surface>
        </Enter>
      </Box>
      <Hand show={typeAt + 6} hide={send + 16} path={[{ f: typeAt + 6, x: 1000, y: 960 }, { f: send, x: 1060, y: 868 }, { f: send + 16, x: 1080, y: 900 }]} clicks={[send]} />
      <Sfx at={send} name="click" volume={0.5} />
      {Array.from({ length: 15 }, (_, i) => <Sfx key={`k${i}`} at={typeAt + Math.round(i / 1.2)} name="click" volume={0.07} />)}
      {settings.map((st) => <Sfx key={st.k} at={st.t} name="tick" volume={0.12} />)}
    </Stage>
  );
};

const Scramble: React.FC<{ from: string; to: string; at: number }> = ({ from, to, at: a }) => {
  const f = useCurrentFrame();
  if (f < a - 12) return <>{from}</>;
  if (f >= a) return <span style={{ color: C.ink }}>{to}</span>;
  return <>{to.split("").map((_, i) => "0123456789abcdef"[(f * 7 + i * 13) % 16]).join("")}</>;
};

export const Protect: React.FC<P> = ({ scene }) => {
  const f = useCurrentFrame();
  const d1 = at(scene, 1) + 3;
  const d2 = at(scene, 2) + 3;
  const d3 = at(scene, 3) + 3;
  const open = prog(f, d3, d3 + 18, EASE);
  const strike = prog(f, d3 + 8, d3 + 20, EASE);
  return (
    <Stage cam={[{ f: 0, z: 1.4, y: 380 }, { f: d1, z: 1.4, y: 440 }, { f: d2, z: 1.4, y: 500 }, { f: d3 + 4, z: 1.36, y: 600 }, { f: d3 + 26, z: 1.36, y: 660 }, { f: scene.frames, z: 1.38, y: 665 }]}>
      <Box x={460} y={150} w={1000}>
        <Enter at={0}>
          <Surface style={{ padding: 36 }}>
            <Title sub="1,762,489 payments" right={f >= d3 + 20 ? <Badge>Protected</Badge> : <Spinner size={30} />}>Protect the data</Title>
            <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 28 }}>
              <Enter at={scene.voiceAt + 2} y={14}>
                <Step done={d1} sub={<Mono style={{ fontSize: 20, color: C.muted, marginTop: 6, display: "block" }}><Scramble from="CUSTOMER_ID 48213" to="6f0b347384a1" at={d1} /></Mono>}>
                  Customer and merchant IDs scrambled
                </Step>
              </Enter>
              <Enter at={scene.voiceAt + 6} y={14}>
                <Step done={d2} sub={<div style={{ fontSize: 20, color: C.muted, marginTop: 6 }}>Card-number columns never reach disk</div>}>Card numbers removed</Step>
              </Enter>
              <Enter at={scene.voiceAt + 10} y={14}>
                <Step done={d3} sub={
                  <div style={{ height: 190 * open, overflow: "hidden", opacity: open }}>
                    <div style={{ marginTop: 16, background: "#fff", border: "1px solid #fecaca", borderRadius: 14, padding: "18px 22px" }}>
                      <Badge tone="danger" size={18}>High severity · Leaks the outcome</Badge>
                      <div style={{ position: "relative", display: "inline-block", marginTop: 14 }}>
                        <Mono style={{ fontSize: 34, color: strike > 0.5 ? C.muted : C.fg }}>TX_FRAUD_SCENARIO</Mono>
                        <div style={{ position: "absolute", left: 0, top: "52%", height: 3, borderRadius: 3, background: C.danger, width: `${strike * 100}%` }} />
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 10 }}>
                        <span style={{ fontSize: 21, color: C.subtle }}>This column would let a model cheat.</span>
                        <span style={{ opacity: prog(f, d3 + 18, d3 + 28) }}><Badge size={18}>Removed before anyone sees it</Badge></span>
                      </div>
                    </div>
                  </div>
                }>
                  Leaky columns caught
                </Step>
              </Enter>
            </div>
          </Surface>
        </Enter>
      </Box>
      <Sfx at={d1} name="tick" volume={0.35} />
      <Sfx at={d2} name="tick" volume={0.35} />
      <Sfx at={d3} name="glitch" volume={0.18} />
      <Sfx at={0} name="whoosh" volume={0.12} />
      <Sfx at={d3 + 18} name="pop" volume={0.16} />
    </Stage>
  );
};

// Late labels: the real split of the sample project, in days.
const SEGS = [
  { k: "Training", d: 73, dates: "Apr 1 – Jun 12" },
  { k: "Gap", d: 30, dates: "Jun 13 – Jul 12" },
  { k: "Public check", d: 7, dates: "Jul 13 – Jul 19" },
  { k: "Private test", d: 14, dates: "Jul 20 – Aug 2" },
  { k: "Too recent to judge", d: 30, dates: "Aug 3 – Sep 1" },
];
export const Holdout: React.FC<P> = ({ scene }) => {
  const f = useCurrentFrame();
  const seal = at(scene, 0, "sealed") - 2;
  const lift = prog(f, seal, seal + 16, OUT);
  const W = 1280;
  const total = SEGS.reduce((s, x) => s + x.d, 0);
  const grow = prog(f, 0, 26, EASE);
  let acc = 0;
  const geo = SEGS.map((s) => {
    const g = { ...s, x: acc, w: (s.d / total) * W - 6 };
    acc += (s.d / total) * W;
    return g;
  });
  const priv = geo[3];
  const px = 270 + 50 + priv.x + priv.w / 2;
  return (
    <Stage cam={[{ f: 0, z: 1.12 }, { f: seal, z: 1.18 }, { f: at(scene, 1), z: 1.6, x: px, y: 500 }, { f: scene.frames, z: 1.66, x: px, y: 500 }]}>
      <Box x={270} y={290} w={1380}>
        <Enter at={0}>
          <Surface style={{ padding: "38px 50px 44px" }}>
            <Title sub="Fraud takes about 30 days to confirm. Models learn and are tested only on what was known at the time.">Late labels</Title>
            <div style={{ position: "relative", height: 26, marginTop: 110 }}>
              {geo.map((s, i) => {
                const isPriv = i === 3;
                const bg = isPriv ? GRAD_X : i === 1 ? "repeating-linear-gradient(135deg, #d4d4d8 0 6px, transparent 6px 12px)" : i === 4 ? "#ececef" : "#c9c9cf";
                const visible = clamp01((grow * W - s.x) / Math.max(1, s.w));
                return (
                  <div key={s.k} style={{ position: "absolute", left: s.x, width: s.w, top: 0, height: 26, borderRadius: 13, background: bg,
                    clipPath: `inset(0 ${(1 - visible) * 100}% 0 0 round 13px)`,
                    transform: isPriv ? `translateY(${-lift * 22}px) scaleY(${1 + lift * 0.3})` : undefined, opacity: isPriv ? 1 : 1 - lift * 0.45,
                    boxShadow: isPriv ? `0 ${12 * lift}px ${30 * lift}px rgba(168,85,247,${0.45 * lift})` : undefined }} />
                );
              })}
              {/* Lock over the sealed days */}
              <div style={{ position: "absolute", left: priv.x + priv.w / 2 - 20, top: -78, opacity: lift, transform: `translateY(${(1 - lift) * 14}px)` }}>
                <svg width={40} height={44} viewBox="0 0 24 26" fill="none">
                  <rect x="3" y="11" width="18" height="13" rx="3.5" fill="#fff" stroke={C.ink} strokeWidth="2" />
                  <path d="M7 11V7.6a5 5 0 0 1 10 0V11" stroke={C.ink} strokeWidth="2" />
                  <circle cx="12" cy="17.4" r="1.8" fill={C.ink} />
                </svg>
              </div>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", rowGap: 16, columnGap: 44, marginTop: 44 }}>
              {SEGS.map((s, i) => (
                <Enter key={s.k} at={10 + i * 3} y={10}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 23, color: i === 3 ? C.fg : C.subtle, fontWeight: i === 3 ? 600 : 400 }}>
                    <span style={{ width: 12, height: 12, borderRadius: 9, background: i === 3 ? GRAD : i === 4 ? "#dcdce0" : "#b8b8bf" }} />
                    {s.k} <Mono style={{ fontSize: 19, color: C.muted }}>{s.dates} · {s.d}d</Mono>
                  </div>
                </Enter>
              ))}
            </div>
          </Surface>
        </Enter>
      </Box>
      <Sfx at={seal} name="shimmer" volume={0.22} />
      <Sfx at={0} name="whoosh" volume={0.12} />
    </Stage>
  );
};

export const V1: React.FC<P> = ({ scene }) => {
  const f = useCurrentFrame();
  const ready = at(scene, 1, "working");
  const money = at(scene, 2);
  return (
    <Stage cam={[{ f: 0, z: 1.5, y: 420 }, { f: money, z: 1.32, y: 470 }, { f: scene.frames, z: 1.28, y: 470 }]}>
      <Box x={410} y={250} w={1100}>
        <Enter at={0}>
          <Surface style={{ padding: "40px 48px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 22, color: C.subtle }}>
              <CheckBox at={ready - 6} size={28} /> Measured on rows it never saw
            </div>
            <div style={{ fontSize: 64, fontWeight: 600, letterSpacing: -2, marginTop: 22, opacity: prog(f, ready - 4, ready + 10), filter: `blur(${(1 - prog(f, ready - 4, ready + 10)) * 8}px)` }}>
              Your model v1 is ready.
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 24, marginTop: 18, opacity: prog(f, money - 6, money + 6) }}>
              <span style={{ fontSize: 130, fontWeight: 650, letterSpacing: -5, backgroundImage: GRAD_X, WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent", lineHeight: 1 }}>
                <CountUp to={3714} at={money - 6} dur={24} />
              </span>
              <span style={{ fontSize: 28, color: C.subtle, lineHeight: 1.35 }}>fraud caught per day<br />in a 200-case queue</span>
            </div>
            <SampleNote />
          </Surface>
        </Enter>
      </Box>
      <Sfx at={money - 6} name="whoosh" volume={0.3} />
      <Sfx at={ready - 6} name="tick" volume={0.14} />
    </Stage>
  );
};

const QROWS = [
  { id: "1474722", amt: "$428.50", risk: "29%", loss: "$125.62", why: ["Unusual amount for this customer", "Unusual activity on this card"] },
  { id: "1472859", amt: "$215.30", risk: "45%", loss: "$95.98", why: ["Unusual amount for this customer", "Customer had recent fraud"] },
  { id: "1468066", amt: "$693.55", risk: "10%", loss: "$72.55", why: ["Unusual amount", "Unusual activity on this card"] },
  { id: "1466459", amt: "$615.65", risk: "11%", loss: "$70.59", why: ["Unusual amount", "Unusual activity at this terminal"] },
];
export const Queue: React.FC<P> = ({ scene }) => {
  const f = useCurrentFrame();
  const why = at(scene, 1);
  const verdict = at(scene, 2);
  const click = verdict + 14;
  const cols = "56px 170px 150px 90px 170px 1fr 260px";
  const TX = 210, TY = 190;
  const rowY = (i: number) => TY + 250 + i * 108;
  return (
    <Stage cam={[{ f: 0, z: 1.02 }, { f: why, z: 1.02 }, { f: why + 20, z: 1.42, x: 1150, y: 560 }, { f: verdict, z: 1.42, x: 1150, y: 560 }, { f: verdict + 18, z: 1.5, x: 1420, y: 470 }, { f: scene.frames, z: 1.52, x: 1420, y: 470 }]}>
      <Box x={TX} y={TY} w={1500}>
        <Enter at={0}>
          <Surface style={{ padding: "36px 40px 18px" }}>
            <Title sub="Today's payments, ranked by expected loss." right={<Badge tone="neutral" dot={false}>Top 200 of 9,637</Badge>}>Review queue</Title>
            <div style={{ display: "grid", gridTemplateColumns: cols, fontSize: 19, color: C.muted, marginTop: 34, paddingBottom: 12, borderBottom: `1px solid ${C.border}` }}>
              {["#", "Transaction", "Amount", "Risk", "Expected loss", "Why", "Verdict"].map((h) => <span key={h}>{h}</span>)}
            </div>
            {QROWS.map((r, i) => {
              const marked = i === 0 && f >= click;
              const dim = f >= verdict && i > 0 ? 0.45 : 1;
              return (
                <Enter key={r.id} at={scene.voiceAt + 2 + i * 4} y={16}>
                  <div style={{ display: "grid", gridTemplateColumns: cols, alignItems: "center", height: 108, borderBottom: i < 3 ? `1px solid ${C.border}` : "none", fontSize: 24, opacity: dim }}>
                    <Mono style={{ color: C.muted }}>{i + 1}</Mono>
                    <Mono>{r.id}</Mono>
                    <Mono>{r.amt}</Mono>
                    <Mono style={{ color: C.subtle }}>{r.risk}</Mono>
                    <Mono style={{ fontWeight: 600 }}>{r.loss}</Mono>
                    <span style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 20, color: f >= why ? C.fg : C.subtle }}>
                      {r.why.map((w) => <span key={w}>{w}</span>)}
                    </span>
                    <span style={{ display: "flex", gap: 10 }}>
                      <span style={{ padding: "9px 18px", borderRadius: 999, fontSize: 20, border: `1.5px solid ${marked ? C.danger : C.border}`, background: marked ? C.dangerBg : "#fff",
                        color: marked ? C.danger : C.subtle, fontWeight: marked ? 600 : 400, transform: `scale(${i === 0 && f >= click - 2 && f < click + 4 ? 0.92 : 1})` }}>
                        {marked ? "● Fraud" : "Fraud"}
                      </span>
                      <span style={{ padding: "9px 18px", borderRadius: 999, fontSize: 20, border: `1.5px solid ${C.border}`, color: C.subtle }}>Not fraud</span>
                    </span>
                  </div>
                </Enter>
              );
            })}
          </Surface>
        </Enter>
      </Box>
      <div style={{ position: "absolute", left: 1290, top: rowY(0) + 66 }}>
        <Enter at={click + 6} y={12}>
          <Surface style={{ padding: "14px 20px", display: "flex", alignItems: "center", gap: 12, borderRadius: 14 }}>
            <CheckBox at={click + 8} size={24} /> <span style={{ fontSize: 21 }}>Saved as a new label</span>
          </Surface>
        </Enter>
      </div>
      <Hand show={verdict} path={[{ f: verdict, x: 1520, y: 640 }, { f: click, x: 1410, y: rowY(0) + 2 }, { f: scene.frames, x: 1418, y: rowY(0) + 12 }]} clicks={[click]} />
      <Sfx at={click} name="click" volume={0.5} />
      {QROWS.map((r, i) => <Sfx key={r.id} at={scene.voiceAt + 2 + i * 4} name="tick" volume={0.08} />)}
      <Sfx at={click + 6} name="pop" volume={0.16} />
    </Stage>
  );
};

const WEEKS = [0.72, 0.75, 0.7, 0.74, 0.73, 0.76, 0.55, 0.52];
export const Drift: React.FC<P> = ({ scene }) => {
  const f = useCurrentFrame();
  const flip = at(scene, 1) + 2;
  const round = at(scene, 2) + 2;
  const slip = prog(f, flip, flip + 12);
  return (
    <Stage cam={[{ f: 0, z: 1.4, y: 430 }, { f: flip, z: 1.42, y: 450 }, { f: round, z: 1.3, y: 620 }, { f: scene.frames, z: 1.3, y: 640 }]}>
      <Box x={500} y={200} w={920}>
        <Enter at={0}>
          <Surface style={{ padding: 40 }}>
            <Title sub="Fraud money caught, by mature week" right={
              <span style={{ position: "relative", display: "inline-block" }}>
                <span style={{ opacity: 1 - slip }}><Badge>Healthy</Badge></span>
                <span style={{ position: "absolute", right: 0, top: 0, opacity: slip, transform: `scale(${0.9 + 0.1 * slip})` }}><Badge tone="warn">Slipping</Badge></span>
              </span>
            }>Health</Title>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 26, height: 220, marginTop: 34 }}>
              {WEEKS.map((w, i) => {
                const late = i >= 6;
                const h = late ? 0.74 + (w - 0.74) * slip : w;
                return <div key={i} style={{ flex: 1, height: 260 * h * prog(f, 2 + i * 2, 18 + i * 2, OUT), borderRadius: 10,
                  background: late && slip > 0.5 ? "linear-gradient(180deg, #fbbf24, #fde68a)" : "linear-gradient(180deg, #a78bfa, #ddd6fe)" }} />;
              })}
            </div>
            <div style={{ fontSize: 24, color: C.warn, marginTop: 22, opacity: slip, fontWeight: 500 }}>New fraud pattern detected.</div>
            <div style={{ height: 120 * prog(f, round - 4, round + 12, EASE), overflow: "hidden" }}>
              <Row style={{ marginTop: 22, padding: "22px 24px", gap: 18 }}>
                <Spinner size={30} />
                <span style={{ fontSize: 27, fontWeight: 500, flex: 1 }}>Improvement round started</span>
                <Badge tone="neutral" dot={false} size={20}>Outside solvers invited</Badge>
              </Row>
            </div>
          </Surface>
        </Enter>
      </Box>
      <Sfx at={flip} name="sub_drop" volume={0.3} />
      <Sfx at={round} name="pop" volume={0.15} />
    </Stage>
  );
};

export const Solvers: React.FC<P> = ({ scene }) => {
  const f = useCurrentFrame();
  const rows = ["Attempt 1", "Attempt 2", "Attempt 3", "Attempt 4", "Attempt 5"];
  return (
    <Stage cam={[{ f: 0, z: 1.5, y: 360 }, { f: scene.frames, z: 1.36, y: 560 }]}>
      <Box x={460} y={170} w={1000}>
        <Enter at={0}>
          <Surface style={{ padding: 38 }}>
            <Title right={<Badge>private holdout</Badge>}>Improvement round</Title>
            <Label style={{ marginTop: 26 }}>Attempts · scored on days the model never saw</Label>
            <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 18 }}>
              {rows.map((r, i) => {
                const a = scene.voiceAt + 2 + i * 6;
                const p = prog(f, a + 6, a + 70 + i * 6, EASE);
                return (
                  <Enter key={r} at={a} y={14}>
                    <Row style={{ padding: "20px 24px", gap: 20 }}>
                      <Spinner size={26} />
                      <span style={{ fontSize: 25, fontWeight: 500, width: 150 }}>{r}</span>
                      <span style={{ fontSize: 21, color: C.subtle, width: 190 }}>outside solver</span>
                      <div style={{ flex: 1, height: 10, borderRadius: 9, background: "#e8e8ec", overflow: "hidden" }}>
                        <div style={{ width: `${p * (62 + i * 7)}%`, height: "100%", background: GRAD_X }} />
                      </div>
                      <Badge tone="neutral" dot={false} size={19}>Scoring</Badge>
                    </Row>
                  </Enter>
                );
              })}
            </div>
          </Surface>
        </Enter>
      </Box>
      <Sfx at={0} name="whoosh" volume={0.12} />
      {[0, 1, 2, 3, 4].map((i) => <Sfx key={i} at={scene.voiceAt + 2 + i * 6} name="tick" volume={0.08} />)}
    </Stage>
  );
};

const GATES = [
  { name: "Hidden data", rule: "Scored on days the solver never saw" },
  { name: "Same rows", rule: "Challenger and champion on identical payments" },
  { name: "Luck test", rule: "Wins in at least 95% of 1,000 resamples" },
  { name: "No segment gets worse", rule: "No group drops more than 5%" },
  { name: "Speed", rule: "10,000 rows in under 5 seconds" },
];
// Same spacing as the gate hits in scripts/music.py.
const gateTick = (scene: SceneInfo, i: number) => scene.voiceAt + Math.round((0.9 + 0.45 * i) * 30);

export const Gates: React.FC<P> = ({ scene }) => {
  const f = useCurrentFrame();
  const count = GATES.filter((_, i) => f >= gateTick(scene, i)).length;
  const done = gateTick(scene, 4) + 8;
  return (
    <Stage cam={[{ f: 0, z: 1.5, y: 330 }, ...GATES.map((_, i) => ({ f: gateTick(scene, i), z: 1.5, y: 380 + i * 62 })), { f: done + 12, z: 1.3, y: 560 }, { f: scene.frames, z: 1.28, y: 570 }]}>
      <Box x={460} y={150} w={1000}>
        <Enter at={0}>
          <Surface style={{ padding: 38 }}>
            <Title right={<Badge tone={count === 5 ? "ok" : "neutral"} dot={count === 5}>{count}/5</Badge>}>Promotion gates</Title>
            <Label style={{ marginTop: 26 }}>Goes live only if all five pass</Label>
            <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 18 }}>
              {GATES.map((g, i) => {
                const t = gateTick(scene, i);
                return (
                  <Row key={g.name} style={{ padding: "18px 24px", gap: 20 }}>
                    <CheckBox at={t} size={30} />
                    <span style={{ fontSize: 26, fontWeight: 500, width: 330, color: f >= t ? C.fg : C.subtle }}>{g.name}</span>
                    <span style={{ fontSize: 21, color: C.subtle, flex: 1 }}>{g.rule}</span>
                  </Row>
                );
              })}
            </div>
            <div style={{ height: 70 * prog(f, done, done + 12, EASE), overflow: "hidden" }}>
              <div style={{ marginTop: 22 }}><Badge size={22}>All five gates passed</Badge></div>
            </div>
          </Surface>
        </Enter>
      </Box>
      <Sfx at={0} name="whoosh" volume={0.12} />
      <Sfx at={done} name="shimmer" volume={0.16} />
    </Stage>
  );
};

export const V2: React.FC<P> = ({ scene }) => {
  const f = useCurrentFrame();
  const swap = scene.voiceAt + 6;
  const more = at(scene, 1);
  const team = at(scene, 2);
  const sw = prog(f, swap, swap + 16, EASE);
  const versions = [
    { v: "v2", note: "Catches $247 more fraud per day", money: "$3,961" },
    { v: "v1", note: "Your first model", money: "$3,714" },
  ];
  return (
    <Stage cam={[{ f: 0, z: 1.45, y: 560 }, { f: swap + 14, z: 1.45, y: 560 }, { f: more + 4, z: 1.5, y: 340 }, { f: team + 4, z: 1.36, y: 420 }, { f: scene.frames, z: 1.32, y: 430 }]}>
      <Box x={460} y={170} w={1000}>
        <Enter at={0}>
          <Surface style={{ padding: "38px 44px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 24, color: C.subtle }}>
              <Badge size={20}>v2</Badge> Fraud caught per day
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 22, marginTop: 14 }}>
              <span style={{ fontSize: 120, fontWeight: 650, letterSpacing: -5, lineHeight: 1, backgroundImage: GRAD_X, WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>
                <CountUp from={3714} to={3961} at={more - 4} dur={24} />
              </span>
              <span style={{ opacity: prog(f, more + 10, more + 20) }}><Badge tone="ok" dot={false} size={24}>+$247</Badge></span>
            </div>
            <div style={{ fontSize: 26, color: f >= team ? C.fg : C.subtle, marginTop: 12, fontWeight: f >= team ? 500 : 400 }}>in the same 200-case queue</div>
            <div style={{ marginTop: 30, position: "relative", height: 2 * 84 + 10 }}>
              {versions.map((r, i) => {
                // v2 drops in on top; v1 slides down and retires.
                const top = i === 0 ? -94 * (1 - sw) : 94 * sw;
                const active = i === 0 ? sw > 0.5 : sw < 0.5;
                return (
                  <Row key={r.v} style={{ position: "absolute", left: 0, right: 0, top, padding: "20px 24px", gap: 20, opacity: i === 0 ? sw : 1 }}>
                    <Badge tone={active ? "ok" : "neutral"} dot={false} size={19}>{active ? "Active" : "Retired"}</Badge>
                    <span style={{ fontSize: 26, fontWeight: 600, width: 50 }}>{r.v}</span>
                    <span style={{ fontSize: 21, color: C.subtle, flex: 1 }}>{r.note}</span>
                    <Mono style={{ fontSize: 25 }}>{r.money}</Mono>
                  </Row>
                );
              })}
            </div>
            <SampleNote />
          </Surface>
        </Enter>
      </Box>
      <Sfx at={swap} name="impact" volume={0.25} />
      <Sfx at={more + 10} name="pop" volume={0.18} />
    </Stage>
  );
};

export const Trust: React.FC<P> = ({ scene }) => {
  const rows = ["The private holdout never leaves the Concours server", "Solvers see training rows only, with scrambled IDs", "Card numbers never reach disk"];
  return (
    <Stage cam={[{ f: 0, z: 1.5, y: 420 }, { f: scene.frames, z: 1.34, y: 520 }]}>
      <Box x={460} y={220} w={1000}>
        <Enter at={0}>
          <Surface style={{ padding: 40 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
              <svg width={40} height={44} viewBox="0 0 24 26" fill="none">
                <rect x="3" y="11" width="18" height="13" rx="3.5" fill={C.okBg} stroke={C.ink} strokeWidth="2" />
                <path d="M7 11V7.6a5 5 0 0 1 10 0V11" stroke={C.ink} strokeWidth="2" />
              </svg>
              <span style={{ fontSize: 38, fontWeight: 600, letterSpacing: -1 }}>What leaves this machine</span>
            </div>
            <div style={{ fontSize: 30, marginTop: 20, color: C.fg }}>Nothing, on its own.</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 24 }}>
              {rows.map((r, i) => (
                <Enter key={r} at={scene.voiceAt + 6 + i * 8} y={12}>
                  <Row style={{ padding: "18px 22px", gap: 18 }}>
                    <CheckBox at={scene.voiceAt + 10 + i * 8} size={28} />
                    <span style={{ fontSize: 24 }}>{r}</span>
                  </Row>
                </Enter>
              ))}
            </div>
          </Surface>
        </Enter>
      </Box>
      <Sfx at={0} name="whoosh" volume={0.12} />
      {[0, 1, 2].map((i) => <Sfx key={i} at={scene.voiceAt + 10 + i * 8} name="tick" volume={0.14} />)}
    </Stage>
  );
};

export const Close: React.FC<P> = ({ scene }) => {
  const f = useCurrentFrame();
  const name = at(scene, 0);
  const p = prog(f, name - 12, name + 16, OUT);
  const fade = prog(f, scene.frames - 24, scene.frames, EASE);
  return (
    <AbsoluteFill style={{ opacity: 1 - fade }}>
      <div style={{ position: "absolute", left: 960 - 340, top: 380, display: "flex", alignItems: "center", gap: 30, opacity: p, filter: `blur(${(1 - p) * 10}px)`,
        transform: `scale(${0.94 + 0.06 * p})` }}>
        <Logo size={136} split={keys(f, [[name, 2.2], [name + 30, 0.7]])} glow={0.5} />
        <span style={{ fontFamily: SANS, fontSize: 148, fontWeight: 600, letterSpacing: -5, color: C.fg }}>Concours</span>
      </div>
      <Line words={wordsOf(scene, 1)} size={50} color={C.subtle} accent={["keep", "up"]} y={640} />
      <Sfx at={name - 2} name="shimmer" volume={0.22} />
    </AbsoluteFill>
  );
};
