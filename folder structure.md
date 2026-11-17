
ROADGUARD-AI/
│
├── apps/
│   ├── web/
│   │   ├── app/
│   │   │   ├── (auth)/
│   │   │   ├── (command)/
│   │   │   │   ├── command/
│   │   │   │   ├── cameras/
│   │   │   │   ├── incidents/
│   │   │   │   ├── hotspots/
│   │   │   │   └── investigations/
│   │   │   ├── (admin)/
│   │   │   │   └── admin/
│   │   │   ├── layout.tsx
│   │   │   └── page.tsx
│   │   ├── components/
│   │   │   ├── ui/
│   │   │   ├── dashboard/
│   │   │   ├── camera/
│   │   │   ├── incidents/
│   │   │   ├── maps/
│   │   │   └── investigations/
│   │   ├── hooks/
│   │   ├── lib/
│   │   ├── services/
│   │   ├── types/
│   │   └── package.json
│   │
│   └── api/
│       ├── app/
│       │   ├── main.py
│       │   ├── core/
│       │   │   ├── config.py
│       │   │   ├── security.py
│       │   │   └── permissions.py
│       │   ├── api/
│       │   │   └── v1/
│       │   │       ├── auth.py
│       │   │       ├── cameras.py
│       │   │       ├── videos.py
│       │   │       ├── incidents.py
│       │   │       ├── hotspots.py
│       │   │       ├── assets.py
│       │   │       ├── investigations.py
│       │   │       └── work_orders.py
│       │   ├── models/
│       │   ├── schemas/
│       │   ├── repositories/
│       │   ├── services/
│       │   ├── middleware/
│       │   └── db/
│       ├── alembic/
│       └── requirements.txt
│
├── ai-engine/
│   ├── detection/
│   │   ├── detector.py
│   │   └── classes.py
│   ├── tracking/
│   │   └── tracker.py
│   ├── events/
│   │   ├── near_miss.py
│   │   ├── collision.py
│   │   ├── wrong_way.py
│   │   ├── sudden_braking.py
│   │   └── signal_violation.py
│   ├── video/
│   │   ├── decoder.py
│   │   ├── processor.py
│   │   └── frame_sampler.py
│   ├── calibration/
│   ├── hotspot/
│   │   ├── clustering.py
│   │   └── risk_scoring.py
│   ├── investigation/
│   │   ├── root_cause.py
│   │   ├── responsibility.py
│   │   └── recommendations.py
│   ├── workers/
│   │   ├── celery_app.py
│   │   └── video_tasks.py
│   └── requirements.txt
│
├── shared/
│   ├── schemas/
│   └── event-contracts/
│
├── infrastructure/
│   ├── docker/
│   ├── nginx/
│   ├── postgres/
│   └── redis/
│
├── scripts/
│   ├── seed_database.py
│   ├── create_admin.py
│   └── import_sample_data.py
│
├── datasets/
│   ├── sample_videos/
│   ├── sample_accidents/
│   └── sample_assets/
│
├── docs/
│   ├── PRD.md
│   ├── TRD.md
│   ├── API_SPEC.md
│   ├── DATABASE.md
│   └── ARCHITECTURE.md
│
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
└── LICENSE
  