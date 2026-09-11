# Viral-ten review

Prepared 2026-09-11. **All ten stories are drafts awaiting human approval. Nothing has
been rendered, narrated, or published.** Each scores 100/100 on the editorial gate; the
only remaining blockers are the three approval blockers, which are a human act.

Selection brief: ten names chosen for TikTok reach, on curve shapes this pipeline renders
well — a long flat run into a wall, a single-year spike, or a fast round trip. Every
premise is counterintuitive on its own data, not merely topical. Names already covered by
`stories/launch-2025/`, `stories/next-2025/` and the 2024 drafts were excluded.

## Data source and its limits

These snapshots come from the **nobodynamed `name-vitals` D1 dataset**, read through the
live connector, not from the SSA archive. Before generating them the connector was checked
against three checked-in archive-derived snapshots — `miley-f`, `kunta-m`, `bertha-f`,
chosen to cover a modern spike, a suppressed/extinct sparse series, and a full 146-year
series. All 200 reported year-observations matched exactly, with no mismatches in either
direction.

That is a counts-level check only. The connector serves no national rank, so the
rank-level anchor verification required by [docs/DATA_VERIFICATION.md](DATA_VERIFICATION.md)
could not be run, and these snapshots therefore **do not claim the SSA archive identity**.
They declare `source_dataset: nobodynamed-d1:name-vitals`; the `Snapshot` model rejects any
attempt to attach an `archive_sha256` to them.

Rank never reaches rendered copy for an approved story — every on-screen line comes from
the StorySpec — so the missing column does not affect these ten videos. It does mean the
snapshots are a weaker provenance than the launch six.

**Required before release.** `stage_release()` now refuses any package whose
`.source.json` declares dataset provenance, so a connector snapshot can be drafted,
scored and approved but cannot be published. Regenerate through the credentialed path so
the ten carry full archive identity and ranks, then re-pin. Locally, with `D1_URL` and
`D1_TOKEN` set:

```sh
uv run python scripts/snapshot_from_d1.py \
  --year 2025 --anchor-dir data/ssa-2025 --out data/nobodynamed-2025 \
  --names Taylor:F Wednesday:F Chad:M Shirley:F Maverick:M \
          Khaleesi:F Luna:F Britney:F Wendy:F Adolph:M \
  --repin-stories stories/viral-2025
```

Re-pinning rewrites each `data_sha256`, which invalidates the approval digest by design.
Approve after re-pinning, not before.

To do the same in CI, add a second extraction step to
`.github/workflows/candidate-snapshots.yaml`. That file is not modified here: the branch
was pushed by an OAuth app without GitHub's `workflow` scope, so a workflow edit is
rejected at push time and has to be made by a human or a token that carries the scope.
Add `research/viral-ten-2025.yaml` to the `paths:` trigger, then, after the existing
extraction step:

```yaml
      - name: Verify D1 mirror and extract viral-ten snapshots
        env:
          D1_URL: ${{ secrets.D1_URL }}
          D1_TOKEN: ${{ secrets.D1_TOKEN }}
        run: |
          uv run python scripts/snapshot_from_d1.py \
            --year 2025 \
            --archive-sha256 cd78e975ed7bb358e018dd62fbe14ced89295e9581c49172ca4eedcb011b3724 \
            --anchor-dir data/ssa-2025 \
            --out out/viral-ten-snapshots \
            --names Taylor:F Wednesday:F Chad:M Shirley:F Maverick:M \
                    Khaleesi:F Luna:F Britney:F Wendy:F Adolph:M

      - name: Upload viral-ten snapshots
        uses: actions/upload-artifact@v4
        with:
          name: viral-ten-snapshots-${{ github.sha }}
          path: out/viral-ten-snapshots/
          retention-days: 30
          if-no-files-found: error
```

Counts are births recorded under each name/sex in SSA data; they do not count everyone
alive with that name. A missing year means fewer than five recorded births, not zero. See
[SSA limitations](https://www.ssa.gov/oact/babynames/limits.html).

## Editorial notes for the reviewer

- **Adolph** is included because the data contradicts the obvious reading: the name had
  already lost 67 percent of its births before January 1933. The copy states only that,
  and makes no claim about why families stopped. Reject it if the subject is off-limits
  regardless of framing.
- **Chad**, **Wednesday** and **Khaleesi** assert *alignment in time* between a cultural
  moment and a break in the curve, never individual parental motive — the same standard
  the launch six use for Alexa.
- **Wendy** says the record contains no Wendys before 1918, fourteen years after Peter Pan
  opened. It deliberately does not claim Barrie invented the name; that is contested and
  the cited sources do not establish it.
- **Taylor** and **Britney** are the two counterintuitive-fame stories. Taylor falls
  through peak fame; Britney's real peak predates the fame by a decade.
- Every number in every line was checked against the pinned snapshot, including the
  "lowest since" claims. Britney's 93 in 2019 is described as a fall, not a floor — the
  all-time series minimum is 7 in 1969.
- No line claims zero births for a year SSA suppressed. Absence from the record means
  fewer than five recorded births, so Wendy and Khaleesi say "no record" and "no reported
  count", never "there were none" or "did not exist".
- **Adolph renders as `long_decline`, not `cultural_rupture`.** The two are not
  interchangeable here: `cultural_rupture` selects the `cultural_event` program, which
  resolves `fixtures/cultural_events.yaml` and would have drawn this name's shared
  marker — "World War II", 1945 — under a headline and narration about 1933. The story's
  own argument is that this is a long decline that predates the rupture, so the archetype
  is also the more accurate one. Chad is the only one of the ten that does draw a marker;
  its anchors now name it ("online slang", 2015) so the reviewer sees what renders.

## Approval

After reviewing each story below, approve individually:

```sh
for s in taylor wednesday chad shirley maverick khaleesi luna britney wendy adolph; do
  uv run nbn story approve stories/viral-2025/$s-2025.yaml --reviewer <name>
done
uv run nbn batch batches/viral-ten.yaml
```

## 1. Taylor — Fame does not save a name

**Kind:** `long_decline` · **Score:** 100/100 · **Target:** 11.5s · **Narration:** 32 words

**Thesis:** Taylor peaked at 21,270 girls in 1993 and fell to 772 in 2025, its lowest count since 1983, through the most lucrative pop career ever recorded.

**Narration (exact draft):**

> Fame does not save a name. Taylor peaked at 21,270 American girls in 1993. The Eras Tour became the highest-grossing tour ever. In 2025: 772. Watch the curve ignore the pop star.

**On-screen:** This name got famous and died anyway. / 21,270 girls in 1993. 772 in 2025. / Peak fame did not slow the decline. / The lowest count since 1983.

**Anchors:** 1993 peak; 2023-2024 Eras Tour years; 2025 floor

**Caption:** Taylor Swift broke every touring record; the name Taylor fell to its lowest count since 1983. #Taylor #NameData #AIVoice

**Comment prompt:** Can a superstar save a name?

**Checked counts:** 1993: 21,270; 2025: 772

**Evidence:** [nobodynamed name-vitals dataset, complete 2025 SSA series](https://www.ssa.gov/oact/babynames/limits.html); [Billboard, Eras Tour final gross](https://www.billboard.com/music/chart-beat/taylor-swift-eras-tour-earnings-2-billion-sales-1235847513/); [NPR, the Eras Tour wrap-up](https://www.npr.org/2024/12/09/nx-s1-5222234/taylor-swift-eras-tour-record-sales)

**Story:** `stories/viral-2025/taylor-2025.yaml`

**Snapshot:** `data/nobodynamed-2025/taylor-f.json`

**Snapshot SHA-256:** `e0e426a8b8fbe3b333550ca8446515e48c44dbfa158c03515e10d1ebd919c3cd`

## 2. Wednesday — The fastest streaming round trip in the record

**Kind:** `cultural_rupture` · **Score:** 100/100 · **Target:** 11.5s · **Narration:** 33 words

**Thesis:** Wednesday peaked at an all-time high of 154 girls in 2023 after the Netflix series, then fell 76 percent to 37 in 2025.

**Narration (exact draft):**

> Netflix made this name a hit. Wednesday hit an all-time high of 154 girls in 2023. The series premiered in November 2022. By 2025 the count was 37. Watch the spike erase itself.

**On-screen:** Netflix made this name. Then unmade it. / 154 girls in 2023. 37 two years later. / The spike gave everything back within two years. / Down 76 percent from the 2023 peak.

**Anchors:** 1965 first reported year; 2023 all-time high; 2025 collapse

**Caption:** Netflix pushed Wednesday to an all-time high in 2023; two years later it gave back 76 percent. #Wednesday #NameData #AIVoice

**Comment prompt:** Which streaming name fades next?

**Checked counts:** 1965: 15; 2023: 154; 2025: 37

**Evidence:** [nobodynamed name-vitals dataset, complete 2025 SSA series](https://www.ssa.gov/oact/babynames/limits.html); [Variety, Wednesday breaks the Netflix weekly viewing record](https://variety.com/2022/tv/news/wednesday-stranger-things-4-record-most-hours-viewed-in-a-week-341-million-1235444385/); [Britannica, The Addams Family television series](https://www.britannica.com/topic/The-Addams-Family-television-series)

**Story:** `stories/viral-2025/wednesday-2025.yaml`

**Snapshot:** `data/nobodynamed-2025/wednesday-f.json`

**Snapshot SHA-256:** `63a68fb9a8cf3923b20531f6a5aa3b58a126437c1c5168f7f5897cb186a44811`

## 3. Chad — A fifty-year slide finished by a meme

**Kind:** `cultural_rupture` · **Score:** 100/100 · **Target:** 11.5s · **Narration:** 34 words

**Thesis:** Chad peaked at 13,392 boys in 1972 and fell to 90 in 2024, its first year under 100 births since 1951, as the internet turned it into a stereotype.

**Narration (exact draft):**

> The internet made this name a punchline. Chad peaked at 13,392 American boys in 1972. By 2024 it was 90 — fewer than any year since 1951. Watch a stereotype finish a slow decline.

**On-screen:** This name became an internet stereotype. / 13,392 boys in 1972. 96 in 2025. / A fifty-year slide, then a meme took the name. / Under 100 births in 2024 — a first since 1951.

**Anchors:** 1972 peak; 2015 event marker, online slang; 2024 record low

**Caption:** Chad slid for fifty years, then the internet turned it into a stereotype. #Chad #NameData #AIVoice

**Comment prompt:** Would you name a kid Chad today?

**Checked counts:** 1972: 13,392; 2024: 90; 2025: 96

**Evidence:** [nobodynamed name-vitals dataset, complete 2025 SSA series](https://www.ssa.gov/oact/babynames/limits.html); [Merriam-Webster slang dictionary, Chad](https://www.merriam-webster.com/slang/chad); [Dictionary.com slang, Chad](https://www.dictionary.com/culture/slang/chad)

**Story:** `stories/viral-2025/chad-2025.yaml`

**Snapshot:** `data/nobodynamed-2025/chad-m.json`

**Snapshot SHA-256:** `662f9e0b9a8063f2ba407510dfed4e13e720186251a62cf3a1d110d4a9f1e162`

## 4. Shirley — The largest short-window surge before the war

**Kind:** `one_hit` · **Score:** 100/100 · **Target:** 12.0s · **Narration:** 34 words

**Thesis:** Shirley nearly tripled from 14,320 births in 1933 to a 42,366 peak in 1935 behind one child star, then fell for ninety years to 133.

**Narration (exact draft):**

> A child star rewrote this name. Shirley went from 14,320 girls in 1933 to 42,366 in 1935. Shirley Temple won a juvenile Academy Award in 1935. By 2025: 133. Watch two years change everything.

**On-screen:** One child star tripled this name. / 14,320 in 1933. 42,366 in 1935. / Two years up, then ninety years down. / 133 births in 2025.

**Anchors:** 1933 base; 1935 peak; 2025 floor

**Caption:** Shirley Temple nearly tripled her own name in two years; ninety years later it is down to 133. #Shirley #NameHistory #AIVoice

**Comment prompt:** Which star moved a name the most?

**Checked counts:** 1933: 14,320; 1935: 42,366; 2025: 133

**Evidence:** [nobodynamed name-vitals dataset, complete 2025 SSA series](https://www.ssa.gov/oact/babynames/limits.html); [Academy of Motion Picture Arts and Sciences, the 7th Academy Awards](https://www.oscars.org/oscars/ceremonies/1935); [Britannica, Bright Eyes](https://www.britannica.com/topic/Bright-Eyes)

**Story:** `stories/viral-2025/shirley-2025.yaml`

**Snapshot:** `data/nobodynamed-2025/shirley-f.json`

**Snapshot SHA-256:** `bb82034d657a1ac9a3b4a30d671386aa0c5cd27446a276fd1b397c527e0322a6`

## 5. Maverick — Two screen pulses, sixty-five years apart

**Kind:** `comeback` · **Score:** 100/100 · **Target:** 11.5s · **Narration:** 34 words

**Thesis:** Maverick fell to six boys in 1967 and returned to an all-time peak of 7,049 in 2022, the year Top Gun: Maverick opened.

**Narration (exact draft):**

> Six boys got this name in 1967. Maverick peaks at 7,049 boys in 2022. Top Gun: Maverick opened that May. The count has fallen every year since. Watch a name follow the box office.

**On-screen:** From 6 boys to 7,049. / 6 in 1967. 7,049 in 2022. / Two screen moments, sixty-five years apart. / A 1957 TV western gave it a smaller first spike.

**Anchors:** 1958 western bump; 1967 low; 2022 all-time peak

**Caption:** Maverick fell to six boys in 1967 and hit an all-time high of 7,049 the year Top Gun: Maverick opened. #Maverick #NameData #AIVoice

**Comment prompt:** Which movie moved a name the most?

**Checked counts:** 1958: 88; 1967: 6; 2022: 7,049; 2025: 5,894

**Evidence:** [nobodynamed name-vitals dataset, complete 2025 SSA series](https://www.ssa.gov/oact/babynames/limits.html); [Britannica, Maverick television series](https://www.britannica.com/topic/Maverick-American-television-series); [Box Office Mojo, Top Gun: Maverick](https://www.boxofficemojo.com/title/tt1745960/)

**Story:** `stories/viral-2025/maverick-2025.yaml`

**Snapshot:** `data/nobodynamed-2025/maverick-m.json`

**Snapshot SHA-256:** `f58aa284e2db3f6d6bb58c2e60bbe90160bcbae378c57d18aa61b2a5184551c1`

## 6. Khaleesi — A name the finale did not kill

**Kind:** `cultural_rupture` · **Score:** 100/100 · **Target:** 11.5s · **Narration:** 33 words

**Thesis:** Khaleesi first appears in 2011, peaked at 565 girls in 2018, fell 29 percent the year after the finale, and still returned 410 births in 2025.

**Narration (exact draft):**

> A TV title became a real name. Khaleesi debuts in 2011 and peaks at 565 in 2018. The show ended in 2019. The next year: 373. Watch a name outlive its own story.

**On-screen:** This name has no record before 2011. / 565 girls in 2018. 410 in 2025. / The finale cost it a third, not its life. / Down 29 percent the year after the ending.

**Anchors:** 2011 first reported year; 2018 peak; 2020 post-finale drop

**Caption:** Game of Thrones put Khaleesi in the birth record, then its own finale knocked the name down 29 percent. #Khaleesi #NameData #AIVoice

**Comment prompt:** Would you still use a name from a show?

**Checked counts:** 2011: 28; 2018: 565; 2020: 373; 2025: 410

**Evidence:** [nobodynamed name-vitals dataset, complete 2025 SSA series](https://www.ssa.gov/oact/babynames/limits.html); [Britannica, Game of Thrones](https://www.britannica.com/topic/Game-of-Thrones); [The Hollywood Reporter, final-season backlash](https://www.hollywoodreporter.com/tv/tv-news/game-thrones-final-season-backlash-female-characters-daenerys-targaryen-twitter-reactions-1210005/)

**Story:** `stories/viral-2025/khaleesi-2025.yaml`

**Snapshot:** `data/nobodynamed-2025/khaleesi-f.json`

**Snapshot SHA-256:** `2b28a979aa73cae3d89c503c51f4290b8b015e3a2c612292dd8d3a8b78dca464`

## 7. Luna — A seventy-year round trip into the top ten

**Kind:** `comeback` · **Score:** 100/100 · **Target:** 12.0s · **Narration:** 35 words

**Thesis:** Luna fell to five girls in 1952, returned to a peak of 8,977 and the national top ten in 2022, then dropped out of the top ten by 2024.

**Narration (exact draft):**

> Five girls got this name in 1952. Luna reaches 8,977 in 2022 and cracks the top ten. By 2024 it was out of the top ten again. Watch a dead name take the top ten.

**On-screen:** This name was nearly gone in 1952. / 5 girls in 1952. 8,977 in 2022. / A seventy-year round trip into the top ten. / Out of the top ten again by 2024.

**Anchors:** 1952 low; 2022 peak; 2024 exit from the top ten

**Caption:** Luna went from five girls in 1952 to the national top ten in 2022, and back out by 2024. #Luna #NameData #AIVoice

**Comment prompt:** Which name cracks the top ten next?

**Checked counts:** 1952: 5; 2022: 8,977; 2025: 6,076

**Evidence:** [nobodynamed name-vitals dataset, complete 2025 SSA series](https://www.ssa.gov/oact/babynames/limits.html); [CBS News, the top baby names of 2022](https://www.cbsnews.com/news/top-baby-names-of-2022-have-been-revealed-ssa/); [CBS News, the top baby names of 2024](https://www.cbsnews.com/news/baby-names-popular-social-security-administration-2024/)

**Story:** `stories/viral-2025/luna-2025.yaml`

**Snapshot:** `data/nobodynamed-2025/luna-f.json`

**Snapshot SHA-256:** `a72b5e7499fe4166bade7812a0beaf4dbcd7715adeecfc59dd7125605bbdef95`

## 8. Britney — The peak came before the fame

**Kind:** `comeback` · **Score:** 100/100 · **Target:** 12.0s · **Narration:** 33 words

**Thesis:** Britney peaked at 2,494 girls in 1989, a decade before the fame, fell to 93 in 2019, and made a comeback to 211 by 2023.

**Narration (exact draft):**

> This name peaked before she was famous. Britney hit 2,494 girls in 1989, ten years early. It fell to 93 by 2019, then climbed back to 211. Watch the second peak fall short.

**On-screen:** This name peaked before she did. / 2,494 in 1989. 2,404 in 2000. / The fame spike never beat the pre-fame peak. / 93 in 2019, the lowest since 1978. 211 in 2023.

**Anchors:** 1989 pre-fame peak; 2000 fame spike; 2019 floor; 2023 rebound

**Caption:** Britney peaked in 1989, a decade before the fame, then fell to its lowest count since 1978 before climbing back. #Britney #NameData #AIVoice

**Comment prompt:** Did the news move this name, or not?

**Checked counts:** 1989: 2,494; 2000: 2,404; 2019: 93; 2023: 211

**Evidence:** [nobodynamed name-vitals dataset, complete 2025 SSA series](https://www.ssa.gov/oact/babynames/limits.html); [Billboard chart rewind, ...Baby One More Time](https://www.billboard.com/music/chart-beat/britney-spears-baby-one-more-time-chart-rewind-1999-1235591427/); [NPR, the conservatorship is terminated](https://www.npr.org/2021/11/12/1055413674/judge-terminates-britney-spears-conservatorship)

**Story:** `stories/viral-2025/britney-2025.yaml`

**Snapshot:** `data/nobodynamed-2025/britney-f.json`

**Snapshot SHA-256:** `770781f2dcdf7d820d79b14bab389599324bd6177588330759d737485702b9f5`

## 9. Wendy — A name with a birthday

**Kind:** `long_decline` · **Score:** 100/100 · **Target:** 12.0s · **Narration:** 35 words

**Thesis:** Wendy is absent from the record until 1918, fourteen years after Peter Pan opened, then rose to a 11,223 peak in 1967 and fell to 165 by 2025.

**Narration (exact draft):**

> The record has no Wendy before 1918. Peter Pan opened in 1904. Wendy enters the record in 1918. It climbs to 11,223 girls in 1967, then falls to 165. Watch a character become a generation.

**On-screen:** This name has a birthday: 1904. / 11,223 girls in 1967. 165 in 2025. / Sixty-three years to the peak. Fifty-eight to fade. / No reported count before 1918.

**Anchors:** 1918 first reported year; 1967 peak; 2025 floor

**Caption:** No Wendy is reported in the US birth record until 1918, fourteen years after Peter Pan opened. #Wendy #NameHistory #AIVoice

**Comment prompt:** What other name came from a book?

**Checked counts:** 1918: 5; 1967: 11,223; 2025: 165

**Evidence:** [nobodynamed name-vitals dataset, complete 2025 SSA series](https://www.ssa.gov/oact/babynames/limits.html); [Britannica, Peter Pan](https://www.britannica.com/topic/Peter-Pan-play-by-Barrie); [Great Ormond Street Hospital Charity, J.M. Barrie](https://www.gosh.org/about-us/peter-pan/history/jm-barrie/)

**Story:** `stories/viral-2025/wendy-2025.yaml`

**Snapshot:** `data/nobodynamed-2025/wendy-f.json`

**Snapshot SHA-256:** `ebe074e6b760f5bf49e46a25b71e2ced9c3295cc0ef418da1d79b018dcb33b5b`

## 10. Adolph — The collapse started sixteen years early

**Kind:** `long_decline` · **Score:** 100/100 · **Target:** 12.0s · **Narration:** 32 words

**Thesis:** Adolph peaked at 673 boys in 1917 and had already fallen 67 percent by 1933, the year Hitler took power, and never recovered.

**Narration (exact draft):**

> This name was already dying before 1933. Adolph peaked at 673 American boys in 1917. By the time Hitler took power it was 222, down sixty-seven percent. Watch the fall start early.

**On-screen:** This name was dying before 1933. / 673 boys in 1917. 222 in 1933. / The collapse started sixteen years before Hitler. / The last reported count is five births, in 2023.

**Anchors:** 1917 peak; 1933 two-thirds down; post-1945 floor

**Caption:** Adolph had already lost two-thirds of its births before Hitler became chancellor in 1933. #Adolph #NameHistory #AIVoice

**Comment prompt:** Did the war kill this name, or just finish it?

**Checked counts:** 1917: 673; 1933: 222; 2023: 5

**Evidence:** [nobodynamed name-vitals dataset, complete 2025 SSA series](https://www.ssa.gov/oact/babynames/limits.html); [US Holocaust Memorial Museum, Hitler is appointed chancellor](https://encyclopedia.ushmm.org/content/en/timeline-event/holocaust/1933-1938/hitler-appointed-chancellor); [Library of Congress, Shadows of War](https://www.loc.gov/classroom-materials/immigration/german/shadows-of-war/)

**Story:** `stories/viral-2025/adolph-2025.yaml`

**Snapshot:** `data/nobodynamed-2025/adolph-m.json`

**Snapshot SHA-256:** `89af433de4df2c5c2a03f6086474abc7008b512c079e0f2d2e0f50844f0c1ac6`

