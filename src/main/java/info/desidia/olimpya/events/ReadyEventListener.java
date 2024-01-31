package info.desidia.olimpya.events;

import net.dv8tion.jda.api.events.GenericEvent;
import net.dv8tion.jda.api.events.session.ReadyEvent;
import net.dv8tion.jda.api.hooks.EventListener;

public class ReadyEventListener implements EventListener {

	public void onEvent(GenericEvent event) {

		if (event instanceof ReadyEvent)
			System.out.println("El bot está listo y online, sigue toqueteando, a ver que encuentras");

	}
}