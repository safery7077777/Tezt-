from aiogram import Router

def get_handlers_router() -> Router:
    from . import common, admin, games
    
    main_router = Router()
    main_router.include_router(common.router)
    main_router.include_router(admin.router)
    main_router.include_router(games.router)
    return main_router
