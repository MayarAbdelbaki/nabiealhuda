/** @odoo-module **/

import { registry } from "@web/core/registry";
import { loadJS, loadCSS } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";
import {
    Component,
    onWillStart,
    onMounted,
    onWillUnmount,
    useEffect,
    useRef,
    useState,
} from "@odoo/owl";

const LEAFLET_VERSION = "1.9.4";
const LEAFLET_CDN = "https://unpkg.com/leaflet@" + LEAFLET_VERSION + "/dist";
const NOMINATIM_URL = "https://nominatim.openstreetmap.org/search";
// Default map center when the record has no coordinates yet (Riyadh, SA).
const DEFAULT_CENTER = { lat: 24.7136, lng: 46.6753 };

export class OsmMapLocation extends Component {
    static template = "delivery_distance.OsmMapLocation";
    static props = {
        "*": true,
    };

    setup() {
        this.mapRef = useRef("map");
        this.map = null;
        this.marker = null;
        this.state = useState({
            query: "",
            results: [],
            searching: false,
        });

        onWillStart(async () => {
            await loadCSS(LEAFLET_CDN + "/leaflet.css");
            await loadJS(LEAFLET_CDN + "/leaflet.js");
        });

        onMounted(() => this._renderMap());

        // Keep the marker in sync when the lat/lng fields change elsewhere
        // (e.g. after the "Locate from Address" button geocodes the address).
        useEffect(
            () => {
                if (this.marker && (this.lat || this.lng)) {
                    const pos = [this.lat, this.lng];
                    this.marker.setLatLng(pos);
                    if (this.map) {
                        this.map.setView(pos, this.map.getZoom());
                    }
                }
            },
            () => [this.lat, this.lng]
        );

        onWillUnmount(() => {
            if (this.map) {
                this.map.remove();
            }
            this.map = null;
            this.marker = null;
        });
    }

    get record() {
        return this.props.record;
    }

    get lat() {
        return this.record.data.partner_latitude || 0;
    }

    get lng() {
        return this.record.data.partner_longitude || 0;
    }

    _renderMap() {
        const L = window.L;
        if (!L || !this.mapRef.el) {
            return;
        }
        // Fix the default marker icon URLs (broken when Leaflet is CDN-loaded).
        delete L.Icon.Default.prototype._getIconUrl;
        L.Icon.Default.mergeOptions({
            iconRetinaUrl: LEAFLET_CDN + "/images/marker-icon-2x.png",
            iconUrl: LEAFLET_CDN + "/images/marker-icon.png",
            shadowUrl: LEAFLET_CDN + "/images/marker-shadow.png",
        });

        const hasCoords = this.lat || this.lng;
        const center = hasCoords
            ? [this.lat, this.lng]
            : [DEFAULT_CENTER.lat, DEFAULT_CENTER.lng];

        this.map = L.map(this.mapRef.el).setView(center, hasCoords ? 15 : 5);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: "© OpenStreetMap contributors",
        }).addTo(this.map);

        this.marker = L.marker(center, { draggable: true }).addTo(this.map);
        this.marker.on("dragend", (ev) => {
            const pos = ev.target.getLatLng();
            this._updateCoords(pos.lat, pos.lng);
        });
        this.map.on("click", (ev) => {
            this.marker.setLatLng(ev.latlng);
            this._updateCoords(ev.latlng.lat, ev.latlng.lng);
        });

        // The container is often sized after the tab/sheet is shown, so the
        // tiles render gray until the map is told to recompute its size.
        setTimeout(() => this.map && this.map.invalidateSize(), 200);
    }

    async _onSearch(ev) {
        if (ev) {
            ev.preventDefault();
        }
        const query = this.state.query.trim();
        if (!query) {
            this.state.results = [];
            return;
        }
        this.state.searching = true;
        try {
            const url =
                NOMINATIM_URL +
                "?format=jsonv2&limit=5&q=" +
                encodeURIComponent(query);
            const response = await fetch(url, {
                headers: { Accept: "application/json" },
            });
            const data = await response.json();
            this.state.results = data.map((item) => ({
                label: item.display_name,
                lat: parseFloat(item.lat),
                lng: parseFloat(item.lon),
            }));
        } catch (error) {
            this.state.results = [];
        } finally {
            this.state.searching = false;
        }
    }

    _onSearchKeydown(ev) {
        // Prevent Enter from saving the form; trigger a search instead.
        if (ev.key === "Enter") {
            ev.preventDefault();
            this._onSearch();
        }
    }

    _selectResult(result) {
        if (this.map && this.marker) {
            const pos = [result.lat, result.lng];
            this.map.setView(pos, 16);
            this.marker.setLatLng(pos);
        }
        this._updateCoords(result.lat, result.lng);
        this.state.results = [];
        this.state.query = result.label;
    }

    async _updateCoords(lat, lng) {
        await this.record.update({
            partner_latitude: lat,
            partner_longitude: lng,
        });
    }
}

export const osmMapLocation = {
    component: OsmMapLocation,
    fieldDependencies: [
        { name: "partner_latitude", type: "float" },
        { name: "partner_longitude", type: "float" },
    ],
};

registry.category("view_widgets").add("osm_map_location", osmMapLocation);
