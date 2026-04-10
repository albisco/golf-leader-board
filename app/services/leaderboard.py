from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.tables import Event, Group, Hole, Score


async def get_leaderboard(db: AsyncSession, event_id: int) -> dict:
    result = await db.execute(
        select(Event).where(Event.id == event_id)
    )
    event = result.scalar_one_or_none()
    if event is None:
        return {"event": None, "groups": []}
    
    result = await db.execute(
        select(Group)
        .options(selectinload(Group.players))
        .where(Group.event_id == event_id)
    )
    groups = result.scalars().all()
    
    result = await db.execute(
        select(Score).where(
            Score.group_id.in_([g.id for g in groups])
        )
    )
    scores = result.scalars().all()
    
    result = await db.execute(
        select(Hole).where(Hole.event_id == event_id)
    )
    holes = result.scalars().all()
    
    hole_by_id = {h.id: h for h in holes}
    scores_by_group = {}
    for score in scores:
        if score.group_id not in scores_by_group:
            scores_by_group[score.group_id] = []
        scores_by_group[score.group_id].append(score)
    
    handicap_per_hole = (1.0 / event.hole_count) if event.hole_count > 0 else 0

    leaderboard = []
    for group in groups:
        group_scores = scores_by_group.get(group.id, [])
        holes_played = len(group_scores)
        gross_total = sum(s.gross_score for s in group_scores)
        net_total = gross_total - group.group_handicap
        running_net = gross_total - round(group.group_handicap * handicap_per_hole * holes_played)

        leaderboard.append({
            "group_id": group.id,
            "group_name": group.name,
            "group_handicap": group.group_handicap,
            "players": [{"name": p.name, "handicap": p.handicap, "is_scorer": p.is_scorer} for p in group.players],
            "holes_played": holes_played,
            "gross_total": gross_total,
            "running_net": running_net,
            "net_total": net_total if holes_played == event.hole_count else None,
            "scores": [
                {
                    "hole_number": hole_by_id[s.hole_id].hole_number,
                    "gross_score": s.gross_score,
                    "edit_count": s.edit_count,
                }
                for s in sorted(group_scores, key=lambda x: hole_by_id[x.hole_id].hole_number)
            ],
        })

    is_final = all(g["holes_played"] == event.hole_count for g in leaderboard)

    if is_final:
        leaderboard.sort(key=lambda x: (x["net_total"] is None, x["net_total"] or 999999, x["gross_total"]))
    else:
        leaderboard.sort(key=lambda x: (x["holes_played"] == 0, -x["holes_played"], x["running_net"], x["gross_total"]))
    
    for i, entry in enumerate(leaderboard):
        entry["rank"] = i + 1
    
    return {
        "event": {
            "id": event.id,
            "name": event.name,
            "date": event.date.isoformat() if event.date else None,
            "hole_count": event.hole_count,
            "status": event.status.value,
        },
        "leaderboard": leaderboard,
        "is_final": is_final,
    }