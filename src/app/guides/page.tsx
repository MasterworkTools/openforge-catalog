import GuidePage from "@/components/guides/guide-page";

/**
 * `/guides` as a whole document.
 *
 * The landmark lives here rather than in `GuidePage`, because that
 * component is also the Guided Builds tab panel inside
 * `MainContentWrapper`'s `main` — so any element it chose for itself
 * would be wrong in one of its two homes.
 */
export default function Guides() {
  return (
    // The viewport height lives here too, for the same reason as the
    // landmark: inside the tab the panel is already sized by
    // `.tabContent`, and a component asking for `h-screen` in both
    // places is taller than one of them.
    <main className="lg:h-screen">
      <GuidePage />
    </main>
  );
}
