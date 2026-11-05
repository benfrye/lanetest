// Candidate archetypes (see research rubric). Order is the display order everywhere:
// left-to-right from the left flank to the center, mainstream last as the reference group.
// Each archetype has a color token AND a shape, because the dark-mode palette sits in the
// CVD warn band and identity must never be color-alone.
export const ARCHETYPES = [
  {
    id: 'progressive',
    label: 'Progressive',
    shape: 'diamond',
    token: '--a-progressive',
    blurb: 'Left on policy, inside the party: Squad-aligned, DSA or Justice Democrats backing, Medicare for All.',
  },
  {
    id: 'left_populist',
    label: 'Left populist',
    shape: 'triangle',
    token: '--a-left-populist',
    blurb: 'The Sanders lane: outsider, anti-billionaire, cost-of-living message, left economics.',
  },
  {
    id: 'center_populist',
    label: 'Center populist',
    shape: 'triangleDown',
    token: '--a-center-populist',
    blurb: 'Outsider and anti-corporate, but culturally moderate: the Osborn and Golden lane.',
  },
  {
    id: 'moderate',
    label: 'Moderate',
    shape: 'square',
    token: '--a-moderate',
    blurb: 'Centrist branding inside the party: Blue Dogs, New Dems, breaks on immigration and spending.',
  },
  {
    id: 'mainstream_liberal',
    label: 'Mainstream liberal',
    shape: 'circle',
    token: '--a-mainstream',
    blurb: 'The party default: standard platform, conventional campaign. The yardstick for the others.',
  },
];

export const ARCHETYPE_BY_ID = Object.fromEntries(ARCHETYPES.map((a) => [a.id, a]));

// Draws a shape of roughly equal visual area for a given radius.
export function drawShape(ctx, shape, x, y, r) {
  ctx.beginPath();
  switch (shape) {
    case 'square': {
      const s = r * 1.77;
      ctx.rect(x - s / 2, y - s / 2, s, s);
      break;
    }
    case 'diamond': {
      const d = r * 1.25;
      ctx.moveTo(x, y - d);
      ctx.lineTo(x + d, y);
      ctx.lineTo(x, y + d);
      ctx.lineTo(x - d, y);
      ctx.closePath();
      break;
    }
    case 'triangle':
    case 'triangleDown': {
      const t = r * 1.55;
      const dir = shape === 'triangle' ? 1 : -1;
      ctx.moveTo(x, y - t * dir);
      ctx.lineTo(x + t * 0.87, y + t * 0.5 * dir);
      ctx.lineTo(x - t * 0.87, y + t * 0.5 * dir);
      ctx.closePath();
      break;
    }
    default:
      ctx.arc(x, y, r, 0, Math.PI * 2);
  }
}

// Same shapes as SVG path strings, centered at 0,0, for legends and inline chips.
export function shapePath(shape, r = 5) {
  switch (shape) {
    case 'square': {
      const s = r * 1.77;
      return `M${-s / 2},${-s / 2}h${s}v${s}h${-s}Z`;
    }
    case 'diamond': {
      const d = r * 1.25;
      return `M0,${-d}L${d},0L0,${d}L${-d},0Z`;
    }
    case 'triangle':
    case 'triangleDown': {
      const t = r * 1.55;
      const dir = shape === 'triangle' ? 1 : -1;
      return `M0,${-t * dir}L${t * 0.87},${t * 0.5 * dir}L${-t * 0.87},${t * 0.5 * dir}Z`;
    }
    default:
      return `M${r},0A${r},${r} 0 1 1 ${-r},0A${r},${r} 0 1 1 ${r},0Z`;
  }
}
