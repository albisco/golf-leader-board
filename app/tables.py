import enum

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class EventFormat(str, enum.Enum):
    ambrose_4ball = "ambrose_4ball"


class EventStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    closed = "closed"


class Organizer(Base):
    __tablename__ = "organizers"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    magic_links = relationship(
        "MagicLink", back_populates="organizer", cascade="all, delete-orphan"
    )
    events = relationship("Event", back_populates="organizer")


class MagicLink(Base):
    """One-time (reusable within expiry) auth token sent to organizer email."""

    __tablename__ = "magic_links"

    id = Column(Integer, primary_key=True)
    organizer_id = Column(
        Integer, ForeignKey("organizers.id", ondelete="CASCADE"), nullable=False
    )
    token = Column(String(128), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    organizer = relationship("Organizer", back_populates="magic_links")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    date = Column(Date, nullable=False)
    format = Column(
        SAEnum(EventFormat, name="event_format"),
        nullable=False,
        default=EventFormat.ambrose_4ball,
    )
    organizer_id = Column(
        Integer, ForeignKey("organizers.id", ondelete="SET NULL"), nullable=True
    )
    join_code = Column(String(32), nullable=False, unique=True, index=True)
    hole_count = Column(Integer, nullable=False, default=18)
    status = Column(
        SAEnum(EventStatus, name="event_status"),
        nullable=False,
        default=EventStatus.draft,
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    organizer = relationship("Organizer", back_populates="events")
    holes = relationship(
        "Hole", back_populates="event", cascade="all, delete-orphan",
        order_by="Hole.hole_number",
    )
    groups = relationship(
        "Group", back_populates="event", cascade="all, delete-orphan",
        order_by="Group.id",
    )
    chat_messages = relationship(
        "ChatMessage", back_populates="event", cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class Hole(Base):
    __tablename__ = "holes"

    id = Column(Integer, primary_key=True)
    event_id = Column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    hole_number = Column(Integer, nullable=False)
    par = Column(Integer, nullable=False)
    notes = Column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("event_id", "hole_number", name="uq_hole_event_number"),)

    event = relationship("Event", back_populates="holes")
    scores = relationship(
        "Score", back_populates="hole", cascade="all, delete-orphan"
    )


class Group(Base):
    """A team of players (4-ball Ambrose group)."""

    __tablename__ = "groups"

    id = Column(Integer, primary_key=True)
    event_id = Column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(100), nullable=False)
    group_handicap = Column(Integer, nullable=False, default=0)
    qr_token = Column(String(128), nullable=False, unique=True, index=True)

    event = relationship("Event", back_populates="groups")
    players = relationship(
        "Player", back_populates="group", cascade="all, delete-orphan",
        order_by="Player.id",
    )
    scores = relationship(
        "Score", back_populates="group", cascade="all, delete-orphan"
    )


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True)
    group_id = Column(
        Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(100), nullable=False)
    handicap = Column(Integer, nullable=False, default=0)
    is_scorer = Column(Boolean, nullable=False, default=False)

    group = relationship("Group", back_populates="players")


class Score(Base):
    """One gross score per group per hole (Ambrose team score)."""

    __tablename__ = "scores"

    id = Column(Integer, primary_key=True)
    group_id = Column(
        Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    hole_id = Column(
        Integer, ForeignKey("holes.id", ondelete="CASCADE"), nullable=False
    )
    gross_score = Column(Integer, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    edit_count = Column(Integer, nullable=False, default=0)

    __table_args__ = (UniqueConstraint("group_id", "hole_id", name="uq_score_group_hole"),)

    group = relationship("Group", back_populates="scores")
    hole = relationship("Hole", back_populates="scores")


class ChatMessage(Base):
    """Event-wide banter — all groups see all messages."""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)
    event_id = Column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    sender_name = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    event = relationship("Event", back_populates="chat_messages")
