import { Compare } from "@/components/Compare";
import { Difference } from "@/components/Difference";
import { Faq } from "@/components/Faq";
import { FinalCta } from "@/components/FinalCta";
import { Footer } from "@/components/Footer";
import { Hero } from "@/components/Hero";
import { HowItWorks } from "@/components/HowItWorks";
import { Nav } from "@/components/Nav";
import { Path } from "@/components/Path";
import { Queue } from "@/components/Queue";
import { Terms } from "@/components/Terms";
import { ThreeWays } from "@/components/ThreeWays";
import { TwoWays } from "@/components/TwoWays";

export default function Home() {
  return (
    <>
      <Nav />
      <main className="px-4 min-[1222px]:px-0">
        {/* Content column with hairline rules on both sides, as in the reference. */}
        <div className="mx-auto max-w-[1190px] overflow-x-clip border-x border-border">
          <Hero />
          <HowItWorks />
          <ThreeWays />
          <Terms />
          <Compare />
          <TwoWays />
          <Queue />
          <Difference />
          <Faq />
          <Path />
          <FinalCta />
          <Footer />
        </div>
      </main>
    </>
  );
}
