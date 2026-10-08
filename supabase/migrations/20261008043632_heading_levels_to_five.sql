-- Part IX nests deeper than the rest of the Manual: Part IX > I. Nazarene Youth
-- International > 810 Charter > A. Local Ministry Plan Template > Ministries. Levels
-- 4 and 5 are those last two. Containment still comes from section_key; level is
-- the heading's depth, for display.
alter table public.nodes drop constraint if exists nodes_level_check;
alter table public.nodes add constraint nodes_level_check check (level between 1 and 5);
